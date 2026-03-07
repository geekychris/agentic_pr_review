"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_diff() -> str:
    return (FIXTURES_DIR / "sample_diff.patch").read_text()


@pytest.fixture
def sample_config_yaml() -> str:
    return """
ai:
  provider: openai
  model: gpt-4o
focus_areas:
  - correctness
  - security
ignore_paths:
  - "*.lock"
linters:
  python:
    enabled: true
    tool: ruff
severity_threshold: suggestion
max_comments: 10
"""
