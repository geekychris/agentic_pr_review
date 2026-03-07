"""Review pipeline — orchestrates the 5-stage review process.

Stages:
  1. Fetch   — PR metadata, diff, full file contents
  2. Plan    — AI planning phase
  3. Analyze — Run analyzers in parallel
  4. Aggregate — Merge, deduplicate, sort findings
  5. Report  — Post to GitHub
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from pathlib import Path

from code_review_agent.ai.base import AIProvider, get_provider
from code_review_agent.ai.prompts import PromptRenderer
from code_review_agent.analyzers.ai_analyzer import AIAnalyzer
from code_review_agent.analyzers.base import BaseAnalyzer
from code_review_agent.analyzers.linter_analyzer import LinterAnalyzer
from code_review_agent.analyzers.security_analyzer import SecurityAnalyzer
from code_review_agent.config import AgentSettings, ReviewConfig, load_config
from code_review_agent.github_client import GitHubClient
from code_review_agent.models import (
    AggregationStats,
    AnalyzerType,
    Finding,
    PRInfo,
    ReviewPlan,
    ReviewResult,
    Severity,
)
from code_review_agent.planner import create_review_plan
from code_review_agent.plugins.loader import discover_plugins
from code_review_agent.reporter import Reporter

logger = logging.getLogger(__name__)


async def run_review(
    owner: str,
    repo: str,
    pr_number: int,
    settings: AgentSettings,
    config_overrides: dict | None = None,
    workspace: str = ".",
) -> ReviewResult:
    """Execute the full review pipeline for a pull request.

    This is the main entry point for the agent.
    """
    async with GitHubClient(settings.github_token) as gh:
        # ── Stage 1: Fetch ──────────────────────────────────────────
        logger.info("Stage 1/5: Fetching PR #%d from %s/%s", pr_number, owner, repo)
        pr = await gh.get_pr(owner, repo, pr_number)

        # Fetch repo config
        repo_config_content = await gh.get_repo_config(owner, repo, pr.head_sha)
        config = load_config(
            repo_config_content=repo_config_content,
            overrides=config_overrides,
        )

        # Filter ignored paths
        pr.diff_files = [
            f for f in pr.diff_files if not _is_ignored(f.path, config.ignore_paths)
        ]

        if not pr.diff_files:
            logger.info("No reviewable files after filtering, skipping review")
            plan = ReviewPlan(reasoning="No files to review after ignore filters.")
            return ReviewResult(plan=plan, summary="No reviewable changes found.")

        # Fetch full file contents for non-deleted files
        logger.info("Fetching full contents for %d files", len(pr.diff_files))
        file_contents = await _fetch_file_contents(gh, pr)

        # ── Stage 2: Plan ───────────────────────────────────────────
        logger.info("Stage 2/5: Planning review")
        ai = _create_ai_provider(config, settings)
        prompts = PromptRenderer()

        try:
            plan = await create_review_plan(pr, config, ai, prompts)
        except Exception:
            logger.exception("Planning failed, using default plan")
            plan = ReviewPlan(
                languages=[],
                focus_areas=config.focus_areas,
                analyzers_to_run=[AnalyzerType.AI, AnalyzerType.LINTER],
                reasoning="Default plan (planning phase failed).",
            )

        # ── Stage 3: Analyze ────────────────────────────────────────
        logger.info("Stage 3/5: Running analyzers")
        analyzers = _build_analyzers(plan, config, settings, ai, prompts, Path(workspace))
        all_findings = await _run_analyzers(analyzers, pr, config, plan, file_contents)

        # ── Stage 4: Aggregate ──────────────────────────────────────
        logger.info("Stage 4/5: Aggregating %d raw findings", len(all_findings))
        findings, agg_stats = _aggregate_findings(all_findings, config)

        # ── Stage 5: Report ─────────────────────────────────────────
        summary = _build_summary(findings, plan, agg_stats)
        result = ReviewResult(
            plan=plan, findings=findings, summary=summary, stats=agg_stats
        )

        if not settings.dry_run:
            logger.info("Stage 5/5: Posting review (%d findings)", len(findings))
            reporter = Reporter(gh)
            await reporter.post_review(pr, result, config)
        else:
            logger.info("Stage 5/5: Dry run — skipping GitHub posting")

        await ai.close()

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_ignored(path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


async def _fetch_file_contents(gh: GitHubClient, pr: PRInfo) -> dict[str, str]:
    """Fetch full file contents for all non-deleted changed files."""
    contents: dict[str, str] = {}

    async def _fetch_one(path: str) -> None:
        fc = await gh.get_file_content(pr.owner, pr.repo, path, pr.head_sha)
        if fc:
            contents[path] = fc.content

    tasks = [
        _fetch_one(f.path) for f in pr.diff_files if f.status != "deleted"
    ]
    await asyncio.gather(*tasks)
    return contents


def _create_ai_provider(config: ReviewConfig, settings: AgentSettings) -> AIProvider:
    return get_provider(
        config.ai.provider,
        api_key=settings.openai_api_key,
        model=config.ai.model,
        org_id=settings.openai_org_id,
    )


def _build_analyzers(
    plan: ReviewPlan,
    config: ReviewConfig,
    settings: AgentSettings,
    ai: AIProvider,
    prompts: PromptRenderer,
    workspace: Path,
) -> list[BaseAnalyzer]:
    """Instantiate the analyzers specified by the plan."""
    analyzers: list[BaseAnalyzer] = []

    for atype in plan.analyzers_to_run:
        if atype == AnalyzerType.AI:
            analyzers.append(AIAnalyzer(ai, prompts))
        elif atype == AnalyzerType.LINTER:
            analyzers.append(LinterAnalyzer(workspace_dir=str(workspace)))
        elif atype == AnalyzerType.SECURITY:
            analyzers.append(SecurityAnalyzer(ai, prompts))
        elif atype == AnalyzerType.PLUGIN:
            analyzers.extend(discover_plugins(workspace))

    # Always load plugins if configured
    if config.plugins:
        plugin_analyzers = discover_plugins(workspace)
        analyzers.extend(plugin_analyzers)

    return analyzers


async def _run_analyzers(
    analyzers: list[BaseAnalyzer],
    pr: PRInfo,
    config: ReviewConfig,
    plan: ReviewPlan,
    file_contents: dict[str, str],
) -> list[Finding]:
    """Run all analyzers concurrently and collect findings."""

    async def _run_one(analyzer: BaseAnalyzer) -> list[Finding]:
        try:
            logger.info("Running analyzer: %s", analyzer.name)
            return await analyzer.analyze(pr, config, plan, file_contents)
        except Exception:
            logger.exception("Analyzer %s failed", analyzer.name)
            return []

    results = await asyncio.gather(*[_run_one(a) for a in analyzers])
    return [f for batch in results for f in batch]


_SEVERITY_TIERS = [Severity.ERROR, Severity.WARNING, Severity.SUGGESTION, Severity.INFO]


def _stratified_limit(findings: list[Finding], limit: int) -> list[Finding]:
    """Select up to *limit* findings while guaranteeing severity diversity.

    Each severity tier that has findings gets at least 1 slot.
    Remaining slots are filled in severity-priority order.
    """
    by_sev: dict[Severity, list[Finding]] = {}
    for f in findings:
        by_sev.setdefault(f.severity, []).append(f)

    selected: list[Finding] = []
    remaining = limit

    # First pass: guarantee 1 from each tier that has findings
    for sev in _SEVERITY_TIERS:
        if remaining > 0 and by_sev.get(sev):
            selected.append(by_sev[sev].pop(0))
            remaining -= 1

    # Second pass: fill remaining slots in severity-priority order
    for sev in _SEVERITY_TIERS:
        while remaining > 0 and by_sev.get(sev):
            selected.append(by_sev[sev].pop(0))
            remaining -= 1

    # Re-sort for consistent output
    selected.sort(key=lambda f: (f.severity.rank, f.file, f.line))
    return selected


def _stratified_limit_per_file(
    findings: list[Finding], per_file_limit: int
) -> tuple[list[Finding], dict[str, int]]:
    """Apply per-file limit with severity diversity within each file."""
    file_groups: dict[str, list[Finding]] = {}
    for f in findings:
        file_groups.setdefault(f.file, []).append(f)

    result: list[Finding] = []
    dropped_by_file: dict[str, int] = {}

    for file_path, file_findings in file_groups.items():
        if len(file_findings) <= per_file_limit:
            result.extend(file_findings)
            continue

        selected = _stratified_limit(file_findings, per_file_limit)
        result.extend(selected)
        dropped = len(file_findings) - len(selected)
        if dropped:
            dropped_by_file[file_path] = dropped

    # Re-sort across all files
    result.sort(key=lambda f: (f.severity.rank, f.file, f.line))
    return result, dropped_by_file


def _aggregate_findings(
    findings: list[Finding], config: ReviewConfig
) -> tuple[list[Finding], AggregationStats]:
    """Deduplicate, filter by severity threshold, limit per-file and globally.

    Returns (filtered_findings, stats) so the summary can report what was dropped.
    """
    stats = AggregationStats(total_raw=len(findings))

    # 1. Severity threshold filtering
    try:
        threshold = Severity(config.severity_threshold)
    except ValueError:
        threshold = Severity.SUGGESTION

    filtered = [f for f in findings if f.severity.rank <= threshold.rank]
    stats.after_threshold = len(filtered)

    # Track what was dropped by severity
    for f in findings:
        if f.severity.rank > threshold.rank:
            stats.dropped_by_severity[f.severity.value] = (
                stats.dropped_by_severity.get(f.severity.value, 0) + 1
            )

    # 2. Deduplicate by file:line:category
    seen: set[str] = set()
    deduped: list[Finding] = []
    for f in filtered:
        key = f.dedup_key
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    stats.after_dedup = len(deduped)

    # 3. Sort: errors first, then warnings, then by file/line
    deduped.sort(key=lambda f: (f.severity.rank, f.file, f.line))

    # 4. Per-file limit — stratified to ensure severity diversity
    if config.max_comments_per_file > 0:
        deduped, dropped_files = _stratified_limit_per_file(
            deduped, config.max_comments_per_file
        )
        stats.dropped_by_file = dropped_files
    stats.after_per_file_limit = len(deduped)

    # 5. Global limit — stratified to keep severity diversity
    if len(deduped) > config.max_comments:
        logger.info(
            "Limiting findings from %d to %d (max_comments)",
            len(deduped),
            config.max_comments,
        )
        deduped = _stratified_limit(deduped, config.max_comments)
    stats.after_global_limit = len(deduped)

    if stats.total_dropped > 0:
        logger.info(
            "Aggregation: %d raw → %d reported (%d dropped: %d below threshold, "
            "%d duplicates, %d per-file limit, %d global limit)",
            stats.total_raw,
            stats.after_global_limit,
            stats.total_dropped,
            stats.total_raw - stats.after_threshold,
            stats.after_threshold - stats.after_dedup,
            stats.after_dedup - stats.after_per_file_limit,
            stats.after_per_file_limit - stats.after_global_limit,
        )

    return deduped, stats


def _build_summary(
    findings: list[Finding],
    plan: ReviewPlan,
    stats: AggregationStats | None = None,
) -> str:
    """Build a markdown summary grouped by severity tier."""
    if not findings:
        return (
            "## Code Review Summary\n\n"
            "No issues found. The changes look good.\n\n"
            f"**Review plan:** {plan.reasoning}"
        )

    # Group by severity
    errors = [f for f in findings if f.severity == Severity.ERROR]
    warnings = [f for f in findings if f.severity == Severity.WARNING]
    suggestions = [f for f in findings if f.severity == Severity.SUGGESTION]
    infos = [f for f in findings if f.severity == Severity.INFO]

    lines = ["## Code Review Summary\n"]
    lines.append(f"Found **{len(findings)}** issue(s):\n")
    for label, group, emoji in [
        ("error", errors, "🔴"),
        ("warning", warnings, "🟡"),
        ("suggestion", suggestions, "🔵"),
        ("info", infos, "\u2139\ufe0f"),
    ]:
        if group:
            lines.append(f"- {emoji} **{len(group)}** {label}(s)")

    # Critical issues — always visible
    if errors:
        lines.append("\n### 🚨 Critical Issues\n")
        for f in sorted(errors, key=lambda x: (x.file, x.line)):
            lines.append(f"- **{f.file}:{f.line}** — {f.title}")

    # Warnings — always visible
    if warnings:
        lines.append("\n### ⚠️ Warnings\n")
        for f in sorted(warnings, key=lambda x: (x.file, x.line)):
            lines.append(f"- **{f.file}:{f.line}** — {f.title}")

    # Suggestions — collapsed
    if suggestions:
        lines.append("\n<details>")
        lines.append(f"<summary>💡 Suggestions ({len(suggestions)})</summary>\n")
        for f in sorted(suggestions, key=lambda x: (x.file, x.line)):
            lines.append(f"- **{f.file}:{f.line}** — {f.title}")
        lines.append("\n</details>")

    # Info — collapsed
    if infos:
        lines.append("\n<details>")
        lines.append(f"<summary>\u2139\ufe0f Info ({len(infos)})</summary>\n")
        for f in sorted(infos, key=lambda x: (x.file, x.line)):
            lines.append(f"- **{f.file}:{f.line}** — {f.title}")
        lines.append("\n</details>")

    # Dropped findings note
    if stats and stats.total_dropped > 0:
        drop_parts = []
        d_threshold = stats.total_raw - stats.after_threshold
        d_dedup = stats.after_threshold - stats.after_dedup
        d_per_file = stats.after_dedup - stats.after_per_file_limit
        d_global = stats.after_per_file_limit - stats.after_global_limit
        if d_threshold:
            drop_parts.append(f"{d_threshold} below severity threshold")
        if d_dedup:
            drop_parts.append(f"{d_dedup} duplicates")
        if d_per_file:
            drop_parts.append(f"{d_per_file} per-file limit")
        if d_global:
            drop_parts.append(f"{d_global} global limit")
        lines.append(
            f"\n_\u2139\ufe0f {stats.total_dropped} finding(s) filtered out: "
            f"{', '.join(drop_parts)}_"
        )

    # Category breakdown
    cat_counts: dict[str, int] = {}
    for f in findings:
        cat_counts[f.category.value] = cat_counts.get(f.category.value, 0) + 1
    if cat_counts:
        lines.append("\n**By category:**")
        for cat, count in sorted(cat_counts.items()):
            lines.append(f"- {cat}: {count}")

    lines.append(f"\n**Review plan:** {plan.reasoning}")
    return "\n".join(lines)
