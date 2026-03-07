"""Tests for pipeline aggregation and helper functions."""

from code_review_agent.config import ReviewConfig
from code_review_agent.models import Category, Finding, Severity
from code_review_agent.pipeline import _aggregate_findings, _is_ignored


def test_is_ignored() -> None:
    assert _is_ignored("package-lock.json", ["*.lock"]) is False
    assert _is_ignored("yarn.lock", ["*.lock"]) is True
    assert _is_ignored("vendor/lib/foo.go", ["vendor/**"]) is True
    assert _is_ignored("src/main.py", ["vendor/**"]) is False


def test_aggregate_deduplication() -> None:
    config = ReviewConfig(max_comments=50)
    findings = [
        Finding(file="a.py", line=10, severity=Severity.ERROR,
                category=Category.SECURITY, title="SQL injection",
                description="found by AI", analyzer="ai"),
        Finding(file="a.py", line=10, severity=Severity.WARNING,
                category=Category.SECURITY, title="SQL injection",
                description="found by linter", analyzer="linter"),
    ]
    result = _aggregate_findings(findings, config)
    # Same file:line:category → deduplicated
    assert len(result) == 1


def test_aggregate_max_comments() -> None:
    config = ReviewConfig(max_comments=3)
    findings = [
        Finding(file=f"f{i}.py", line=1, severity=Severity.WARNING,
                category=Category.STYLE, title=f"issue {i}", description="")
        for i in range(10)
    ]
    result = _aggregate_findings(findings, config)
    assert len(result) == 3


def test_aggregate_severity_filtering() -> None:
    config = ReviewConfig(severity_threshold="warning")
    findings = [
        Finding(file="a.py", line=1, severity=Severity.ERROR,
                category=Category.CORRECTNESS, title="Error", description=""),
        Finding(file="a.py", line=2, severity=Severity.WARNING,
                category=Category.STYLE, title="Warning", description=""),
        Finding(file="a.py", line=3, severity=Severity.SUGGESTION,
                category=Category.STYLE, title="Suggestion", description=""),
    ]
    result = _aggregate_findings(findings, config)
    # Suggestion should be filtered out (threshold is warning)
    assert len(result) == 2
    severities = {f.severity for f in result}
    assert Severity.SUGGESTION not in severities
