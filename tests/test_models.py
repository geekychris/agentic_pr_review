"""Tests for core data models."""

from code_review_agent.models import (
    Category,
    Finding,
    ReviewPlan,
    ReviewResult,
    Severity,
)


def test_severity_ordering() -> None:
    assert Severity.ERROR < Severity.WARNING
    assert Severity.WARNING < Severity.SUGGESTION
    assert Severity.SUGGESTION < Severity.INFO


def test_finding_dedup_key() -> None:
    f = Finding(
        file="src/auth.py",
        line=10,
        severity=Severity.ERROR,
        category=Category.SECURITY,
        title="SQL injection",
        description="...",
    )
    assert f.dedup_key == "src/auth.py:10:security"


def test_review_result_has_errors() -> None:
    plan = ReviewPlan()
    result = ReviewResult(
        plan=plan,
        findings=[
            Finding(
                file="a.py",
                line=1,
                severity=Severity.ERROR,
                category=Category.CORRECTNESS,
                title="Bug",
                description="...",
            )
        ],
    )
    assert result.has_errors is True


def test_review_result_no_errors() -> None:
    plan = ReviewPlan()
    result = ReviewResult(
        plan=plan,
        findings=[
            Finding(
                file="a.py",
                line=1,
                severity=Severity.WARNING,
                category=Category.STYLE,
                title="Style",
                description="...",
            )
        ],
    )
    assert result.has_errors is False


def test_findings_by_severity() -> None:
    plan = ReviewPlan()
    result = ReviewResult(
        plan=plan,
        findings=[
            Finding(file="a.py", line=1, severity=Severity.ERROR,
                    category=Category.CORRECTNESS, title="e", description=""),
            Finding(file="a.py", line=2, severity=Severity.WARNING,
                    category=Category.STYLE, title="w", description=""),
            Finding(file="a.py", line=3, severity=Severity.ERROR,
                    category=Category.SECURITY, title="e2", description=""),
        ],
    )
    by_sev = result.findings_by_severity
    assert len(by_sev[Severity.ERROR]) == 2
    assert len(by_sev[Severity.WARNING]) == 1
