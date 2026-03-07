"""Linter analyzer — runs language-specific linters and filters to changed lines."""

from __future__ import annotations

import logging

from code_review_agent.analyzers.base import BaseAnalyzer
from code_review_agent.config import ReviewConfig
from code_review_agent.diff_parser import get_language
from code_review_agent.linters.base import get_linter
from code_review_agent.models import Finding, PRInfo, ReviewPlan

logger = logging.getLogger(__name__)


class LinterAnalyzer(BaseAnalyzer):
    """Runs the appropriate linter for each changed file's language.

    Findings are filtered to only lines present in the diff, so
    pre-existing warnings are not reported.
    """

    name = "linter"

    def __init__(self, workspace_dir: str = ".") -> None:
        self._workspace = workspace_dir

    async def analyze(
        self,
        pr: PRInfo,
        config: ReviewConfig,
        plan: ReviewPlan,
        file_contents: dict[str, str],
    ) -> list[Finding]:
        all_findings: list[Finding] = []

        # Group files by language
        files_by_lang: dict[str, list[str]] = {}
        changed_lines_map: dict[str, set[int]] = {}
        for diff_file in pr.diff_files:
            if diff_file.status == "deleted":
                continue
            lang = get_language(diff_file.path)
            if lang:
                files_by_lang.setdefault(lang, []).append(diff_file.path)
                changed_lines_map[diff_file.path] = diff_file.changed_lines

        for lang, files in files_by_lang.items():
            linter = get_linter(lang, config)
            if linter is None:
                logger.debug("No linter configured for %s", lang)
                continue

            logger.info("Running %s linter on %d files", lang, len(files))
            try:
                findings = await linter.run(files, workspace=self._workspace)
            except Exception:
                logger.exception("Linter %s failed", linter.name)
                continue

            # Filter to changed lines only
            for f in findings:
                changed = changed_lines_map.get(f.file, set())
                if f.line in changed:
                    all_findings.append(f)
                else:
                    logger.debug(
                        "Filtered linter finding on unchanged line %d in %s", f.line, f.file
                    )

        return all_findings
