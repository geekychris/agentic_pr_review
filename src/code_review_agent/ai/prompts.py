"""Prompt template loading and rendering with Jinja2."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Default prompts directory (shipped inside the package)
_BUILTIN_PROMPTS_DIR = Path(__file__).resolve().parent / "templates"


class PromptRenderer:
    """Renders Jinja2 prompt templates.

    Template resolution order:
    1. Repo-local overrides  (``.codereview/prompts/``)
    2. Built-in templates    (``prompts/`` in the project root)
    """

    def __init__(self, extra_dirs: list[Path] | None = None) -> None:
        search_paths: list[str] = []
        # Repo overrides come first so they shadow built-ins
        if extra_dirs:
            for d in extra_dirs:
                if d.is_dir():
                    search_paths.append(str(d))
        search_paths.append(str(_BUILTIN_PROMPTS_DIR))

        self._env = Environment(
            loader=FileSystemLoader(search_paths),
            autoescape=select_autoescape([]),
            keep_trailing_newline=True,
        )

    def render(self, template_name: str, **context: object) -> str:
        """Render a template by filename (e.g. ``planning.md.j2``)."""
        tmpl = self._env.get_template(template_name)
        return tmpl.render(**context)

    def available_templates(self) -> list[str]:
        """List all template names visible to the renderer."""
        return sorted(self._env.loader.list_templates())  # type: ignore[union-attr]
