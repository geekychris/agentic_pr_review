"""Go linter using golangci-lint."""

from __future__ import annotations

import json
import logging

from code_review_agent.linters.base import BaseLinter
from code_review_agent.models import Category, Finding, Severity

logger = logging.getLogger(__name__)


class GoLinter(BaseLinter):
    name = "golangci-lint"
    language = "go"

    async def run(self, files: list[str], workspace: str = ".") -> list[Finding]:
        # golangci-lint operates on packages, not individual files.
        # We run it on the whole workspace and filter results to our file set.
        cmd = ["golangci-lint", "run", "--out-format=json", "--issues-exit-code=0", "./..."]
        _returncode, stdout, _stderr = await self._run_command(cmd, cwd=workspace)

        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse golangci-lint JSON: %s", stdout[:200])
            return []

        file_set = set(files)
        findings: list[Finding] = []

        for issue in data.get("Issues", []) or []:
            pos = issue.get("Pos", {})
            filepath = pos.get("Filename", "")
            if filepath not in file_set:
                continue

            sev_text = issue.get("Severity", "warning")
            severity = Severity.ERROR if sev_text == "error" else Severity.WARNING

            findings.append(
                Finding(
                    file=filepath,
                    line=pos.get("Line", 0),
                    severity=severity,
                    category=Category.LINTER,
                    title=f"{issue.get('FromLinter', 'golangci-lint')}: {issue.get('Text', '')}",
                    description=issue.get("Text", ""),
                    rule_id=issue.get("FromLinter", ""),
                    analyzer="linter/golangci-lint",
                )
            )
        return findings
