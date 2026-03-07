"""Rust linter using cargo clippy."""

from __future__ import annotations

import json
import logging

from code_review_agent.linters.base import BaseLinter
from code_review_agent.models import Category, Finding, Severity

logger = logging.getLogger(__name__)


class RustLinter(BaseLinter):
    name = "clippy"
    language = "rust"

    async def run(self, files: list[str], workspace: str = ".") -> list[Finding]:
        # clippy operates on the whole crate; filter results to changed files.
        cmd = [
            "cargo", "clippy", "--message-format=json", "--quiet", "--", "-W", "clippy::all",
        ]
        _returncode, stdout, _stderr = await self._run_command(cmd, cwd=workspace)

        file_set = set(files)
        findings: list[Finding] = []

        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            if msg.get("reason") != "compiler-message":
                continue

            message = msg.get("message", {})
            level = message.get("level", "warning")
            if level not in ("warning", "error"):
                continue

            # Get primary span
            spans = message.get("spans", [])
            primary = next((s for s in spans if s.get("is_primary")), None)
            if not primary:
                continue

            filepath = primary.get("file_name", "")
            if filepath not in file_set:
                continue

            severity = Severity.ERROR if level == "error" else Severity.WARNING

            suggestion = None
            if primary.get("suggested_replacement") is not None:
                suggestion = primary["suggested_replacement"]

            findings.append(
                Finding(
                    file=filepath,
                    line=primary.get("line_start", 0),
                    end_line=primary.get("line_end"),
                    severity=severity,
                    category=Category.LINTER,
                    title=f"clippy: {message.get('message', '')}",
                    description=message.get("message", ""),
                    rule_id=message.get("code", {}).get("code", "") if message.get("code") else "",
                    analyzer="linter/clippy",
                    suggestion=suggestion,
                )
            )
        return findings
