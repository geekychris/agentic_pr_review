"""Security-focused analyzer — a dedicated AI pass for security vulnerabilities."""

from __future__ import annotations

import logging

from code_review_agent.ai.base import AIProvider
from code_review_agent.ai.prompts import PromptRenderer
from code_review_agent.analyzers.base import BaseAnalyzer
from code_review_agent.config import ReviewConfig
from code_review_agent.diff_parser import get_language
from code_review_agent.models import Category, Finding, PRInfo, ReviewPlan, Severity

logger = logging.getLogger(__name__)


class SecurityAnalyzer(BaseAnalyzer):
    """Dedicated security review pass using the AI provider.

    This is separate from the general AI analyzer to allow it to be
    enabled/disabled independently and to use a security-specific prompt.
    """

    name = "security"

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
        # If the plan already includes security in focus_areas and the AI
        # analyzer will handle it, skip to avoid duplicates.
        if "security" in plan.focus_areas and "ai" in [a.value for a in plan.analyzers_to_run]:
            logger.info("Security review covered by AI analyzer; skipping dedicated pass")
            return []

        all_findings: list[Finding] = []

        for diff_file in pr.diff_files:
            if diff_file.status == "deleted":
                continue

            full_content = file_contents.get(diff_file.path, "")
            language = get_language(diff_file.path) or ""

            # Build diff text
            diff_lines: list[str] = []
            for hunk in diff_file.hunks:
                diff_lines.append(hunk.header)
                for dl in hunk.lines:
                    prefix = "+" if dl.is_addition else "-" if dl.is_deletion else " "
                    diff_lines.append(f"{prefix}{dl.content}")

            prompt = self._prompts.render(
                "review_security.md.j2",
                pr_title=pr.title,
                file_path=diff_file.path,
                language=language,
                full_content=full_content,
                diff="\n".join(diff_lines),
                custom_instructions=config.custom_instructions,
            )

            result = await self._ai.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=config.ai.temperature,
                max_tokens=config.ai.max_tokens,
            )

            if "error" in result:
                continue

            changed = diff_file.changed_lines
            for raw in result.get("findings", []):
                line = raw.get("line", 0)
                if line and line not in changed:
                    continue
                try:
                    sev = Severity(raw.get("severity", "warning"))
                except ValueError:
                    sev = Severity.WARNING

                all_findings.append(
                    Finding(
                        file=diff_file.path,
                        line=line,
                        end_line=raw.get("end_line"),
                        severity=sev,
                        category=Category.SECURITY,
                        title=raw.get("title", "Security Issue"),
                        description=raw.get("description", ""),
                        suggestion=raw.get("suggestion"),
                        analyzer="security",
                    )
                )

        return all_findings
