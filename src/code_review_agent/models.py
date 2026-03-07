"""Core data models for the code review agent."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Severity(StrEnum):
    """Finding severity levels, ordered from most to least severe."""

    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {
            Severity.ERROR: 0,
            Severity.WARNING: 1,
            Severity.SUGGESTION: 2,
            Severity.INFO: 3,
        }[self]

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Severity):
            return NotImplemented
        return self.rank < other.rank


class Category(StrEnum):
    """Finding category."""

    CORRECTNESS = "correctness"
    SECURITY = "security"
    PERFORMANCE = "performance"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    BEST_PRACTICE = "best_practice"
    LINTER = "linter"
    OTHER = "other"


class AnalyzerType(StrEnum):
    """Types of available analyzers."""

    AI = "ai"
    LINTER = "linter"
    SECURITY = "security"
    PLUGIN = "plugin"


# ---------------------------------------------------------------------------
# Diff models
# ---------------------------------------------------------------------------


class DiffLine(BaseModel):
    """A single line within a diff hunk."""

    content: str
    old_lineno: int | None = None  # None for additions
    new_lineno: int | None = None  # None for deletions
    is_addition: bool = False
    is_deletion: bool = False
    is_context: bool = False
    diff_position: int = 0  # Position in the overall diff (for GitHub API)


class DiffHunk(BaseModel):
    """A hunk within a file diff."""

    header: str  # e.g. "@@ -10,5 +10,7 @@"
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: list[DiffLine] = Field(default_factory=list)


class DiffFile(BaseModel):
    """A single file's diff."""

    path: str
    old_path: str | None = None  # For renames
    status: str = "modified"  # added, modified, deleted, renamed
    hunks: list[DiffHunk] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0

    @property
    def changed_lines(self) -> set[int]:
        """Return set of new-file line numbers that were added/modified."""
        lines: set[int] = set()
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.is_addition and line.new_lineno is not None:
                    lines.add(line.new_lineno)
        return lines

    def diff_position_for_line(self, new_lineno: int) -> int | None:
        """Map a new-file line number to a diff position for GitHub API."""
        for hunk in self.hunks:
            for line in hunk.lines:
                if line.new_lineno == new_lineno:
                    return line.diff_position
        return None


# ---------------------------------------------------------------------------
# PR models
# ---------------------------------------------------------------------------


class PRInfo(BaseModel):
    """Pull request metadata."""

    owner: str
    repo: str
    number: int
    title: str = ""
    description: str = ""
    base_sha: str = ""
    head_sha: str = ""
    base_ref: str = ""
    head_ref: str = ""
    author: str = ""
    diff_files: list[DiffFile] = Field(default_factory=list)
    raw_diff: str = ""


class FileContent(BaseModel):
    """Full content of a file at a specific ref."""

    path: str
    content: str
    ref: str  # The git ref (SHA or branch) this content is from


# ---------------------------------------------------------------------------
# Review models
# ---------------------------------------------------------------------------


class ReviewPlan(BaseModel):
    """Output of the planning phase — what the review should focus on."""

    languages: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    priority_files: list[str] = Field(default_factory=list)
    analyzers_to_run: list[AnalyzerType] = Field(default_factory=list)
    reasoning: str = ""  # Why the planner chose this plan
    estimated_complexity: str = "medium"  # low, medium, high


class Finding(BaseModel):
    """A single review finding (issue, suggestion, or comment)."""

    file: str
    line: int
    end_line: int | None = None
    severity: Severity
    category: Category
    title: str
    description: str
    suggestion: str | None = None  # Suggested code replacement
    analyzer: str = ""  # Which analyzer produced this finding
    rule_id: str | None = None  # Linter rule ID if applicable
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """Key for deduplication: same file + line + similar message."""
        return f"{self.file}:{self.line}:{self.category.value}"


class AggregationStats(BaseModel):
    """Tracks what was dropped during finding aggregation."""

    total_raw: int = 0
    after_threshold: int = 0
    after_dedup: int = 0
    after_per_file_limit: int = 0
    after_global_limit: int = 0
    dropped_by_severity: dict[str, int] = Field(default_factory=dict)
    dropped_by_file: dict[str, int] = Field(default_factory=dict)

    @property
    def total_dropped(self) -> int:
        return self.total_raw - self.after_global_limit


class ReviewResult(BaseModel):
    """Aggregated output from all analyzers."""

    plan: ReviewPlan
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""
    error: str | None = None
    stats: AggregationStats = Field(default_factory=AggregationStats)

    @property
    def findings_by_severity(self) -> dict[Severity, list[Finding]]:
        result: dict[Severity, list[Finding]] = {}
        for f in self.findings:
            result.setdefault(f.severity, []).append(f)
        return result

    @property
    def has_errors(self) -> bool:
        return any(f.severity == Severity.ERROR for f in self.findings)
