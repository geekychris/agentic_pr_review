"""Tests for configuration loading."""

from code_review_agent.config import ReviewConfig, load_config


def test_default_config() -> None:
    config = ReviewConfig()
    assert config.ai.provider == "openai"
    assert config.ai.model == "gpt-4o"
    assert "correctness" in config.focus_areas
    assert config.max_comments == 25
    assert config.linters.python.tool == "ruff"


def test_from_yaml_string(sample_config_yaml: str) -> None:
    config = ReviewConfig.from_yaml_string(sample_config_yaml)
    assert config.ai.model == "gpt-4o"
    assert config.focus_areas == ["correctness", "security"]
    assert config.max_comments == 10


def test_load_config_with_overrides() -> None:
    config = load_config(overrides={"max_comments": 50})
    assert config.max_comments == 50
    # Other defaults preserved
    assert config.ai.provider == "openai"


def test_severity_threshold_default() -> None:
    config = ReviewConfig()
    assert config.severity_threshold == "suggestion"
