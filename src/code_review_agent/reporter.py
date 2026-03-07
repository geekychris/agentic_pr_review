"""Posts review results to GitHub as PR reviews with inline comments."""

from __future__ import annotations

import contextlib
import logging
from collections import defaultdict
from typing import Any

import httpx

from code_review_agent.config import ReviewConfig
from code_review_agent.github_client import GitHubClient
from code_review_agent.models import Finding, PRInfo, ReviewResult, Severity

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    Severity.ERROR: "🔴",
    Severity.WARNING: "🟡",
    Severity.SUGGESTION: "🔵",
    Severity.INFO: "ℹ️",  # noqa: RUF001
}


class Reporter:
    """Converts ReviewResult into GitHub API calls."""

    def __init__(self, gh: GitHubClient) -> None:
        self._gh = gh

    async def post_review(
        self, pr: PRInfo, result: ReviewResult, config: ReviewConfig | None = None
    ) -> None:
        """Post the full review to GitHub.

        Creates a single PR review with:
        - Inline comments for findings at or above inline_threshold
        - A summary body grouping all findings by severity tier
        """
        if not result.findings:
            await self._gh.post_comment(pr.owner, pr.repo, pr.number, result.summary)
            return

        # Determine inline threshold
        inline_threshold = Severity.WARNING
        if config:
            with contextlib.suppress(ValueError):
                inline_threshold = Severity(config.inline_threshold)

        # Split findings: inline-eligible vs summary-only
        inline_findings = [
            f for f in result.findings if f.severity.rank <= inline_threshold.rank
        ]
        summary_only_findings = [
            f for f in result.findings if f.severity.rank > inline_threshold.rank
        ]

        # Build inline comments (skipping findings that can't be mapped to the diff)
        comments: list[dict[str, Any]] = []
        unmapped_findings: list[Finding] = []
        for finding in inline_findings:
            comment = self._build_inline_comment(finding, pr)
            if comment:
                comments.append(comment)
            else:
                unmapped_findings.append(finding)

        # Build enhanced summary with severity tiers
        summary = self._build_summary(
            result, pr, len(comments), unmapped_findings, summary_only_findings
        )

        # Determine review event
        event = "COMMENT"
        if result.has_errors:
            event = "REQUEST_CHANGES"

        if not comments:
            # No inline comments could be mapped — post summary with all findings
            await self._gh.post_comment(pr.owner, pr.repo, pr.number, summary)
            return

        # GitHub API limits to 50 comments per review
        if len(comments) <= 50:
            await self._post_single_review(pr, summary, event, comments)
        else:
            await self._post_batched_reviews(pr, summary, event, comments)

    async def _post_single_review(
        self,
        pr: PRInfo,
        summary: str,
        event: str,
        comments: list[dict[str, Any]],
    ) -> None:
        """Post a single review with all comments."""
        try:
            await self._gh.create_review(
                owner=pr.owner,
                repo=pr.repo,
                pr_number=pr.number,
                commit_sha=pr.head_sha,
                body=summary,
                event=event,
                comments=comments,
            )
            logger.info("Posted review with %d inline comments (event=%s)", len(comments), event)
        except Exception as exc:
            # GitHub returns 422 if you try REQUEST_CHANGES on your own PR.
            # Retry with COMMENT event before falling back to plain comment.
            resp_text = ""
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                resp_text = exc.response.text.lower()
            exc_str = (str(exc) + resp_text).lower()
            if event != "COMMENT" and (
                "request changes" in exc_str or "your own pull request" in exc_str
            ):
                logger.warning(
                    "Cannot %s on own PR, retrying with COMMENT event", event
                )
                try:
                    await self._gh.create_review(
                        owner=pr.owner,
                        repo=pr.repo,
                        pr_number=pr.number,
                        commit_sha=pr.head_sha,
                        body=summary,
                        event="COMMENT",
                        comments=comments,
                    )
                    logger.info(
                        "Posted review with %d inline comments (event=COMMENT)",
                        len(comments),
                    )
                    return
                except Exception:
                    logger.exception("Retry with COMMENT event also failed")

            logger.exception(
                "Failed to post review with inline comments, falling back to plain comment"
            )
            # Final fallback: post as a regular issue comment
            body = summary + "\n\n" + self._findings_as_markdown(comments)
            await self._gh.post_comment(pr.owner, pr.repo, pr.number, body)

    async def _post_batched_reviews(
        self,
        pr: PRInfo,
        summary: str,
        event: str,
        comments: list[dict[str, Any]],
    ) -> None:
        """Post multiple reviews when comments exceed GitHub's 50-comment limit."""
        batch_size = 50
        for i in range(0, len(comments), batch_size):
            batch = comments[i : i + batch_size]
            batch_event = event if i == 0 else "COMMENT"
            batch_body = summary if i == 0 else f"_Continued review ({i + 1}-{i + len(batch)})_"

            try:
                await self._gh.create_review(
                    owner=pr.owner,
                    repo=pr.repo,
                    pr_number=pr.number,
                    commit_sha=pr.head_sha,
                    body=batch_body,
                    event=batch_event,
                    comments=batch,
                )
            except Exception:
                logger.exception("Failed to post review batch starting at %d", i)

    def _build_inline_comment(
        self, finding: Finding, pr: PRInfo
    ) -> dict[str, Any] | None:
        """Convert a Finding into a GitHub review comment dict.

        Uses diff `position` (the 1-based offset from the first @@ of the file)
        which is the most reliable parameter for the GitHub Reviews API.
        Falls back to `line` + `side` + `subject_type` if position lookup fails.
        """
        diff_file = next((f for f in pr.diff_files if f.path == finding.file), None)
        if diff_file is None:
            logger.warning("Finding references unknown file: %s", finding.file)
            return None

        # Build comment body
        emoji = SEVERITY_EMOJI.get(finding.severity, "")
        body_parts = [
            f"**{emoji} {finding.severity.value.upper()}: {finding.title}**",
            "",
            finding.description,
        ]

        # Add code suggestion using GitHub's suggestion syntax
        if finding.suggestion:
            body_parts.extend([
                "",
                "```suggestion",
                finding.suggestion,
                "```",
            ])

        body_parts.append(f"\n_[{finding.analyzer}]_")

        body = "\n".join(body_parts)

        # Verify the line is within the diff (GitHub rejects comments on lines
        # that aren't part of the diff hunks)
        if finding.line not in diff_file.changed_lines:
            # Try to find the closest changed line in the same hunk
            closest = self._closest_diff_line(diff_file, finding.line)
            if closest is None:
                logger.debug(
                    "Line %d not in diff for %s, skipping inline comment",
                    finding.line,
                    finding.file,
                )
                return None
            target_line = closest
        else:
            target_line = finding.line

        comment: dict[str, Any] = {
            "path": finding.file,
            "body": body,
            "line": target_line,
            "side": "RIGHT",
        }

        # Multi-line comment
        if (
            finding.end_line
            and finding.end_line != finding.line
            and finding.end_line in diff_file.changed_lines
        ):
            comment["start_line"] = target_line
            comment["start_side"] = "RIGHT"
            comment["line"] = finding.end_line

        return comment

    @staticmethod
    def _closest_diff_line(diff_file: Any, target: int) -> int | None:
        """Find the closest changed line to *target* in the same hunk."""
        changed = diff_file.changed_lines
        if not changed:
            return None
        # Pick the changed line nearest to the target
        return min(changed, key=lambda ln: abs(ln - target))

    def _build_summary(
        self,
        result: ReviewResult,
        pr: PRInfo,
        inline_count: int,
        unmapped: list[Finding],
        summary_only: list[Finding] | None = None,
    ) -> str:
        """Build a summary grouped by severity tier."""
        parts: list[str] = []
        summary_only = summary_only or []

        total = len(result.findings)
        parts.append("## 🔍 Code Review Summary\n")
        parts.append(
            f"Found **{total}** issue(s) across "
            f"**{len(self._files_set(result.findings))}** file(s).\n"
        )

        if inline_count:
            parts.append(
                f"📌 **{inline_count}** inline comment(s) added to the code below.\n"
            )

        # Severity counts
        severity_counts: dict[str, int] = defaultdict(int)
        for f in result.findings:
            severity_counts[f.severity.value] += 1
        severity_line = " | ".join(
            f"{SEVERITY_EMOJI.get(Severity(k), '')} {v} {k}(s)"
            for k, v in sorted(severity_counts.items())
        )
        parts.append(f"**Severity:** {severity_line}\n")

        # Group findings by severity tier
        errors = [f for f in result.findings if f.severity == Severity.ERROR]
        warnings = [f for f in result.findings if f.severity == Severity.WARNING]
        suggestions = [f for f in result.findings if f.severity == Severity.SUGGESTION]
        infos = [f for f in result.findings if f.severity == Severity.INFO]

        # Critical — always visible and prominent
        if errors:
            parts.append("### 🚨 Critical Issues\n")
            for f in sorted(errors, key=lambda x: (x.file, x.line)):
                parts.append(f"- **{f.file}:{f.line}** — {f.title}")
            parts.append("")

        # Warnings — always visible
        if warnings:
            parts.append("### ⚠️ Warnings\n")
            for f in sorted(warnings, key=lambda x: (x.file, x.line)):
                parts.append(f"- **{f.file}:{f.line}** — {f.title}")
            parts.append("")

        # Suggestions — collapsed
        if suggestions:
            parts.append("<details>")
            parts.append(
                f"<summary>💡 Suggestions ({len(suggestions)})</summary>\n"
            )
            for f in sorted(suggestions, key=lambda x: (x.file, x.line)):
                parts.append(f"- **{f.file}:{f.line}** — {f.title}")
            parts.append("\n</details>\n")

        # Info — collapsed
        if infos:
            parts.append("<details>")
            parts.append(f"<summary>\u2139\ufe0f Info ({len(infos)})</summary>\n")
            for f in sorted(infos, key=lambda x: (x.file, x.line)):
                parts.append(f"- **{f.file}:{f.line}** — {f.title}")
            parts.append("\n</details>\n")

        # Summary-only findings (below inline threshold)
        if summary_only:
            parts.append("<details>")
            parts.append(
                f"<summary>📋 Summary-only findings ({len(summary_only)}) "
                f"— below inline comment threshold</summary>\n"
            )
            for f in sorted(
                summary_only, key=lambda x: (x.severity.rank, x.file, x.line)
            ):
                emoji = SEVERITY_EMOJI.get(f.severity, "")
                parts.append(
                    f"- **{f.file}:{f.line}** {emoji} {f.title} — {f.description}"
                )
            parts.append("\n</details>\n")

        # Dropped findings stats
        if result.stats and result.stats.total_dropped > 0:
            stats = result.stats
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
            parts.append(
                f"_\u2139\ufe0f {stats.total_dropped} finding(s) filtered out: "
                f"{', '.join(drop_parts)}_\n"
            )

        # Review plan reasoning
        if result.plan.reasoning:
            parts.append("### Review Approach\n")
            parts.append(f"{result.plan.reasoning}\n")

        # Unmapped findings (couldn't be placed inline)
        if unmapped:
            parts.append("### Additional Findings (not in diff)\n")
            for f in unmapped:
                emoji = SEVERITY_EMOJI.get(f.severity, "")
                parts.append(
                    f"- **{f.file}:{f.line}** {emoji} **{f.title}** — {f.description}"
                )
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _files_set(findings: list[Finding]) -> set[str]:
        return {f.file for f in findings}

    @staticmethod
    def _findings_as_markdown(comments: list[dict[str, Any]]) -> str:
        """Format findings as markdown (fallback when review API fails)."""
        lines = ["### Detailed Findings\n"]
        for c in comments:
            lines.append(f"**{c['path']}:{c.get('line', c.get('position', '?'))}**")
            lines.append(c["body"])
            lines.append("")
        return "\n".join(lines)
