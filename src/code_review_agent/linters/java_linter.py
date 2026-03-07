"""Java linter using checkstyle."""

from __future__ import annotations

import logging
import re

from code_review_agent.linters.base import BaseLinter
from code_review_agent.models import Category, Finding, Severity

logger = logging.getLogger(__name__)

# checkstyle default output: [WARN] /path/File.java:10:5: message [RuleId]
_CHECKSTYLE_RE = re.compile(
    r"\[(WARN|ERROR|INFO)]\s+(.+?):(\d+)(?::(\d+))?:\s+(.+?)(?:\s+\[(.+?)])?"
)


class JavaLinter(BaseLinter):
    name = "checkstyle"
    language = "java"

    async def run(self, files: list[str], workspace: str = ".") -> list[Finding]:
        # checkstyle needs a config; use Google style as default
        cmd = [
            "checkstyle",
            "-c", "/google_checks.xml",
            *files,
        ]
        _returncode, stdout, stderr = await self._run_command(cmd, cwd=workspace)

        output = stdout + stderr
        findings: list[Finding] = []

        for match in _CHECKSTYLE_RE.finditer(output):
            level, filepath, lineno, _col, message, rule_id = match.groups()
            severity = Severity.ERROR if level == "ERROR" else Severity.WARNING

            findings.append(
                Finding(
                    file=filepath,
                    line=int(lineno),
                    severity=severity,
                    category=Category.LINTER,
                    title=f"checkstyle: {message.strip()}",
                    description=message.strip(),
                    rule_id=rule_id or "",
                    analyzer="linter/checkstyle",
                )
            )
        return findings
