"""Python linter using ruff."""

from __future__ import annotations

import json
import logging

from code_review_agent.linters.base import BaseLinter
from code_review_agent.models import Category, Finding, Severity

logger = logging.getLogger(__name__)


class PythonLinter(BaseLinter):
    name = "ruff"
    language = "python"

    async def run(self, files: list[str], workspace: str = ".") -> list[Finding]:
        cmd = ["ruff", "check", "--output-format=json", "--no-fix", *files]
        _returncode, stdout, _stderr = await self._run_command(cmd, cwd=workspace)

        if not stdout.strip():
            return []

        try:
            results = json.loads(stdout)
        except json.JSONDecodeError:
            logger.error("Failed to parse ruff JSON output: %s", stdout[:200])
            return []

        findings: list[Finding] = []
        for item in results:
            rule = item.get("code", "")
            severity = Severity.WARNING
            if rule and rule.startswith(("E9", "F")):
                severity = Severity.ERROR

            findings.append(
                Finding(
                    file=item.get("filename", ""),
                    line=item.get("location", {}).get("row", 0),
                    severity=severity,
                    category=Category.LINTER,
                    title=f"ruff {rule}: {item.get('message', '')}",
                    description=item.get("message", ""),
                    rule_id=rule,
                    analyzer="linter/ruff",
                    suggestion=_extract_fix(item),
                )
            )
        return findings


def _extract_fix(item: dict) -> str | None:
    """Extract a suggested fix from ruff's fix data if available."""
    fix = item.get("fix")
    if not fix:
        return None
    edits = fix.get("edits", [])
    if not edits:
        return None
    # ruff provides edit content; use the first one as a simple suggestion
    return edits[0].get("content")
