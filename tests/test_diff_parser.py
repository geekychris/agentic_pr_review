"""Tests for the diff parser."""

from code_review_agent.diff_parser import detect_languages, get_language, parse_diff


def test_parse_diff_basic(sample_diff: str) -> None:
    files = parse_diff(sample_diff)
    assert len(files) == 2

    # First file: new file src/auth.py
    auth = files[0]
    assert auth.path == "src/auth.py"
    assert auth.status == "added"
    assert auth.additions == 15
    assert auth.deletions == 0
    assert len(auth.hunks) == 1

    # Second file: modified src/utils.py
    utils = files[1]
    assert utils.path == "src/utils.py"
    assert utils.status == "modified"
    assert utils.additions == 7
    assert utils.deletions == 2


def test_changed_lines(sample_diff: str) -> None:
    files = parse_diff(sample_diff)
    auth = files[0]
    # New file: all lines are "changed"
    assert 1 in auth.changed_lines
    assert 15 in auth.changed_lines


def test_diff_position(sample_diff: str) -> None:
    files = parse_diff(sample_diff)
    auth = files[0]
    # Line 1 should have a diff position
    pos = auth.diff_position_for_line(1)
    assert pos is not None
    assert pos > 0


def test_get_language() -> None:
    assert get_language("foo.py") == "python"
    assert get_language("Bar.java") == "java"
    assert get_language("main.go") == "go"
    assert get_language("lib.rs") == "rust"
    assert get_language("README.md") is None


def test_detect_languages(sample_diff: str) -> None:
    files = parse_diff(sample_diff)
    langs = detect_languages(files)
    assert langs == ["python"]
