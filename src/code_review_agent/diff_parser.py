"""Parse unified diffs into structured DiffFile / DiffHunk models."""

from __future__ import annotations

import re

from code_review_agent.models import DiffFile, DiffHunk, DiffLine

DIFF_HEADER_RE = re.compile(r"^diff --git a/(.+?) b/(.+)$")
HUNK_HEADER_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
RENAME_FROM_RE = re.compile(r"^rename from (.+)$")
RENAME_TO_RE = re.compile(r"^rename to (.+)$")


def parse_diff(raw_diff: str) -> list[DiffFile]:
    """Parse a unified diff string into a list of DiffFile objects.

    Each DiffFile contains hunks with line-level detail including:
    - old/new line numbers
    - whether the line is an addition, deletion, or context
    - the diff_position (1-indexed offset from the first @@ of that file),
      which is what GitHub's review-comment API requires.
    """
    files: list[DiffFile] = []
    current_file: DiffFile | None = None
    current_hunk: DiffHunk | None = None

    # Position counter resets per file — it is the 1-based offset from the
    # first @@ header of the file.  GitHub uses this for inline review comments.
    file_position = 0

    for raw_line in raw_diff.splitlines():
        # ----- file header -----
        header_match = DIFF_HEADER_RE.match(raw_line)
        if header_match:
            current_file = DiffFile(
                path=header_match.group(2),
                old_path=header_match.group(1),
            )
            files.append(current_file)
            current_hunk = None
            file_position = 0
            continue

        if current_file is None:
            continue

        # Detect file status from diff metadata lines
        if raw_line.startswith("new file"):
            current_file.status = "added"
            continue
        if raw_line.startswith("deleted file"):
            current_file.status = "deleted"
            continue
        if raw_line.startswith("similarity index"):
            current_file.status = "renamed"
            continue
        rename_from = RENAME_FROM_RE.match(raw_line)
        if rename_from:
            current_file.old_path = rename_from.group(1)
            continue
        rename_to = RENAME_TO_RE.match(raw_line)
        if rename_to:
            current_file.path = rename_to.group(1)
            continue

        # Skip --- and +++ headers
        if raw_line.startswith("---") or raw_line.startswith("+++"):
            continue

        # ----- hunk header -----
        hunk_match = HUNK_HEADER_RE.match(raw_line)
        if hunk_match:
            file_position += 1  # The @@ line itself counts as a position
            current_hunk = DiffHunk(
                header=raw_line,
                old_start=int(hunk_match.group(1)),
                old_count=int(hunk_match.group(2) or "1"),
                new_start=int(hunk_match.group(3)),
                new_count=int(hunk_match.group(4) or "1"),
            )
            current_file.hunks.append(current_hunk)
            _old_lineno = current_hunk.old_start
            _new_lineno = current_hunk.new_start
            continue

        if current_hunk is None:
            continue

        file_position += 1

        # ----- diff content lines -----
        if raw_line.startswith("+"):
            line = DiffLine(
                content=raw_line[1:],
                new_lineno=_new_lineno,
                is_addition=True,
                diff_position=file_position,
            )
            current_hunk.lines.append(line)
            current_file.additions += 1
            _new_lineno += 1

        elif raw_line.startswith("-"):
            line = DiffLine(
                content=raw_line[1:],
                old_lineno=_old_lineno,
                is_deletion=True,
                diff_position=file_position,
            )
            current_hunk.lines.append(line)
            current_file.deletions += 1
            _old_lineno += 1

        elif raw_line.startswith(" ") or raw_line == "":
            content = raw_line[1:] if raw_line.startswith(" ") else raw_line
            line = DiffLine(
                content=content,
                old_lineno=_old_lineno,
                new_lineno=_new_lineno,
                is_context=True,
                diff_position=file_position,
            )
            current_hunk.lines.append(line)
            _old_lineno += 1
            _new_lineno += 1

        elif raw_line.startswith("\\"):
            # "\ No newline at end of file" — skip but consume position
            pass

    return files


def get_language(path: str) -> str | None:
    """Infer programming language from file extension."""
    ext_map = {
        ".py": "python",
        ".pyi": "python",
        ".java": "java",
        ".go": "go",
        ".rs": "rust",
        ".js": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".jsx": "javascript",
        ".rb": "ruby",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".kt": "kotlin",
        ".swift": "swift",
        ".sh": "shell",
        ".bash": "shell",
    }
    for ext, lang in ext_map.items():
        if path.endswith(ext):
            return lang
    return None


def detect_languages(diff_files: list[DiffFile]) -> list[str]:
    """Return sorted, unique list of languages in the changed files."""
    langs: set[str] = set()
    for df in diff_files:
        lang = get_language(df.path)
        if lang:
            langs.add(lang)
    return sorted(langs)
