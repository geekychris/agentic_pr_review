"""AI-powered code review analyzer.

Sends each changed file to the AI with focus-specific prompts and
full file context for correctness validation.
"""

from __future__ import annotations

import logging
from typing import Any

from code_review_agent.ai.base import AIProvider
from code_review_agent.ai.prompts import PromptRenderer
from code_review_agent.analyzers.base import BaseAnalyzer
from code_review_agent.config import ReviewConfig
from code_review_agent.diff_parser import get_language
from code_review_agent.models import Category, DiffFile, Finding, PRInfo, ReviewPlan, Severity

logger = logging.getLogger(__name__)

# Maps focus area names to prompt template filenames
FOCUS_TEMPLATES = {
    "correctness": "review_correctness.md.j2",
    "security": "review_security.md.j2",
    "performance": "review_performance.md.j2",
    "style": "review_style.md.j2",
}


class AIAnalyzer(BaseAnalyzer):
    """Analyzer that uses an LLM to review code changes."""

    name = "ai"

    def __init__(self, ai: AIProvider, prompts: PromptRenderer) -> None:
        self._ai = ai
        self._prompts = prompts

    async def analyze(
        self,
        pr: PRInfo,
        config: ReviewConfig,
        plan: ReviewPlan,
        file_contents: dict[str, str],
    ) -> list[Finding]:
        all_findings: list[Finding] = []

        for diff_file in pr.diff_files:
            if diff_file.status == "deleted":
                continue

            full_content = file_contents.get(diff_file.path, "")
            file_diff = _render_file_diff(diff_file)
            language = get_language(diff_file.path)

            for focus_area in plan.focus_areas:
                template = FOCUS_TEMPLATES.get(focus_area)
                if not template:
                    logger.debug("No template for focus area: %s", focus_area)
                    continue

                findings = await self._review_file(
                    pr=pr,
                    config=config,
                    diff_file=diff_file,
                    full_content=full_content,
                    file_diff=file_diff,
                    language=language or "",
                    template=template,
                    focus_area=focus_area,
                )
                all_findings.extend(findings)

        return all_findings

    async def _review_file(
        self,
        pr: PRInfo,
        config: ReviewConfig,
        diff_file: DiffFile,
        full_content: str,
        file_diff: str,
        language: str,
        template: str,
        focus_area: str,
    ) -> list[Finding]:
        """Review a single file for a single focus area."""
        prompt = self._prompts.render(
            template,
            pr_title=pr.title,
            file_path=diff_file.path,
            language=language,
            full_content=full_content,
            diff=file_diff,
            custom_instructions=config.custom_instructions,
        )

        logger.debug("AI reviewing %s [%s]", diff_file.path, focus_area)

        result = await self._ai.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=config.ai.temperature,
            max_tokens=config.ai.max_tokens,
        )

        if "error" in result:
            logger.warning(
                "AI review failed for %s [%s]: %s",
                diff_file.path,
                focus_area,
                result.get("error"),
            )
            return []

        return _parse_findings(
            result.get("findings", []),
            file_path=diff_file.path,
            analyzer_name=f"ai/{focus_area}",
            changed_lines=diff_file.changed_lines,
        )


def _render_file_diff(diff_file: DiffFile) -> str:
    """Reconstruct the diff text for a single file from parsed hunks."""
    lines: list[str] = []
    for hunk in diff_file.hunks:
        lines.append(hunk.header)
        for dl in hunk.lines:
            if dl.is_addition:
                lines.append(f"+{dl.content}")
            elif dl.is_deletion:
                lines.append(f"-{dl.content}")
            else:
                lines.append(f" {dl.content}")
    return "\n".join(lines)


def _parse_findings(
    raw_findings: list[dict[str, Any]],
    file_path: str,
    analyzer_name: str,
    changed_lines: set[int],
) -> list[Finding]:
    """Parse AI JSON findings into Finding models, filtering to changed lines."""
    findings: list[Finding] = []
    for raw in raw_findings:
        line = raw.get("line", 0)
        # Only report findings on lines that actually changed
        if line and line not in changed_lines:
            logger.debug("Skipping finding on unchanged line %d in %s", line, file_path)
            continue

        try:
            severity = Severity(raw.get("severity", "suggestion"))
        except ValueError:
            severity = Severity.SUGGESTION

        try:
            category = Category(raw.get("category", "other"))
        except ValueError:
            category = Category.OTHER

        findings.append(
            Finding(
                file=file_path,
                line=line,
                end_line=raw.get("end_line"),
                severity=severity,
                category=category,
                title=raw.get("title", "AI Finding"),
                description=raw.get("description", ""),
                suggestion=raw.get("suggestion"),
                analyzer=analyzer_name,
            )
        )
    return findings
