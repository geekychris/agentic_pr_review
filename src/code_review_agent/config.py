"""Configuration management for the code review agent."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

CONFIG_FILENAME = ".codereview.yml"


# ---------------------------------------------------------------------------
# Sub-configs
# ---------------------------------------------------------------------------


class AIConfig(BaseModel):
    """AI provider configuration."""

    provider: str = "openai"
    model: str = "gpt-4o"
    temperature: float = 0.1
    max_tokens: int = 4096


class LinterToolConfig(BaseModel):
    """Configuration for a single linter."""

    enabled: bool = True
    tool: str = ""
    extra_args: list[str] = Field(default_factory=list)


class LintersConfig(BaseModel):
    """Per-language linter configuration."""

    python: LinterToolConfig = Field(default_factory=lambda: LinterToolConfig(tool="ruff"))
    java: LinterToolConfig = Field(default_factory=lambda: LinterToolConfig(tool="checkstyle"))
    go: LinterToolConfig = Field(default_factory=lambda: LinterToolConfig(tool="golangci-lint"))
    rust: LinterToolConfig = Field(default_factory=lambda: LinterToolConfig(tool="clippy"))


# ---------------------------------------------------------------------------
# Main config
# ---------------------------------------------------------------------------


class ReviewConfig(BaseModel):
    """Per-repo review configuration, loaded from .codereview.yml."""

    ai: AIConfig = Field(default_factory=AIConfig)
    focus_areas: list[str] = Field(
        default_factory=lambda: ["correctness", "security", "performance", "style"]
    )
    ignore_paths: list[str] = Field(
        default_factory=lambda: ["*.lock", "vendor/**", "generated/**", "node_modules/**"]
    )
    linters: LintersConfig = Field(default_factory=LintersConfig)
    severity_threshold: str = "suggestion"
    inline_threshold: str = "warning"  # Only post inline comments for findings >= this severity
    max_comments: int = 25
    max_comments_per_file: int = 10
    plugins: list[str] = Field(default_factory=list)
    custom_instructions: str = ""

    @classmethod
    def from_yaml(cls, path: Path) -> ReviewConfig:
        """Load configuration from a YAML file."""
        if not path.exists():
            logger.info("No config file at %s, using defaults", path)
            return cls()
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    @classmethod
    def from_yaml_string(cls, content: str) -> ReviewConfig:
        """Load configuration from a YAML string (e.g. fetched from GitHub)."""
        data = yaml.safe_load(content) or {}
        return cls.model_validate(data)


class AgentSettings(BaseSettings):
    """Environment-level settings (secrets, runtime flags)."""

    github_token: str = ""
    openai_api_key: str = ""
    openai_org_id: str = ""
    log_level: str = "INFO"
    dry_run: bool = False  # If true, don't post to GitHub
    debug: bool = False

    model_config = {"env_prefix": "CRA_", "env_file": ".env", "extra": "ignore"}


def load_config(
    repo_config_content: str | None = None,
    local_path: Path | None = None,
    overrides: dict[str, Any] | None = None,
) -> ReviewConfig:
    """Load config with precedence: overrides > repo file > defaults."""
    if repo_config_content:
        config = ReviewConfig.from_yaml_string(repo_config_content)
    elif local_path:
        config = ReviewConfig.from_yaml(local_path)
    else:
        config = ReviewConfig()

    if overrides:
        data = config.model_dump()
        data.update(overrides)
        config = ReviewConfig.model_validate(data)

    return config
