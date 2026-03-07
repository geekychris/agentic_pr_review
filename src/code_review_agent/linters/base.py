"""Abstract base class for language-specific linters."""

from __future__ import annotations

import asyncio
import logging
import shutil
from abc import ABC, abstractmethod

from code_review_agent.config import ReviewConfig
from code_review_agent.models import Finding

logger = logging.getLogger(__name__)


class BaseLinter(ABC):
    """Interface for language-specific linters.

    Each linter wraps an external tool (ruff, checkstyle, clippy, etc.)
    and converts its output to a list of Finding objects.
    """

    name: str = "base"
    language: str = "unknown"

    @abstractmethod
    async def run(self, files: list[str], workspace: str = ".") -> list[Finding]:
        """Run the linter on the given files and return findings.

        Parameters
        ----------
        files : list[str]
            Relative file paths within the workspace.
        workspace : str
            Root directory of the checked-out repo.
        """

    @staticmethod
    async def _run_command(
        cmd: list[str], cwd: str = "."
    ) -> tuple[int, str, str]:
        """Run a subprocess and return (returncode, stdout, stderr)."""
        logger.debug("Running: %s", " ".join(cmd))
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
        )

    @staticmethod
    def is_available(tool_name: str) -> bool:
        """Check if a linter tool is available on PATH."""
        return shutil.which(tool_name) is not None


def get_linter(language: str, config: ReviewConfig) -> BaseLinter | None:
    """Factory: return the appropriate linter for a language, or None."""
    from code_review_agent.linters.go_linter import GoLinter
    from code_review_agent.linters.java_linter import JavaLinter
    from code_review_agent.linters.python_linter import PythonLinter
    from code_review_agent.linters.rust_linter import RustLinter

    linter_map: dict[str, tuple[type[BaseLinter], str]] = {
        "python": (PythonLinter, config.linters.python.tool),
        "java": (JavaLinter, config.linters.java.tool),
        "go": (GoLinter, config.linters.go.tool),
        "rust": (RustLinter, config.linters.rust.tool),
    }

    entry = linter_map.get(language)
    if entry is None:
        return None

    cls, tool_name = entry

    # Check if linter is enabled in config
    lang_config = getattr(config.linters, language, None)
    if lang_config and not lang_config.enabled:
        logger.debug("Linter for %s is disabled in config", language)
        return None

    if not BaseLinter.is_available(tool_name):
        logger.warning("Linter tool %s not found on PATH, skipping %s", tool_name, language)
        return None

    return cls()
