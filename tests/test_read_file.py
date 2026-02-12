"""
Tests for read_file functionality.
"""

# pylint: disable=redefined-outer-name, unused-argument

import os
import sys
import pytest

# Ensure app is importable
sys.path.append(os.getcwd())

from app.services import git_ops  # pylint: disable=wrong-import-position


@pytest.fixture
def mock_codebase(tmp_path, mocker):
    """Sets up a temporary codebase root."""
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", str(tmp_path))
    return tmp_path


def test_read_file_normal(mock_codebase):
    """Test reading a normal file."""
    # Create a file with 10 lines
    file_content = "\n".join([f"Line {i}" for i in range(1, 11)])
    test_file = mock_codebase / "test.txt"
    test_file.write_text(file_content, encoding="utf-8")

    # Read the file
    content = git_ops.read_file("test.txt")
    assert content == file_content


def test_read_file_large_truncation(mock_codebase):
    """Test truncation of large files (manual check)."""
    # Create a file with 2500 lines
    lines = [f"Line {i}" for i in range(1, 2501)]
    file_content = "\n".join(lines)
    test_file = mock_codebase / "large.txt"
    test_file.write_text(file_content, encoding="utf-8")

    content = git_ops.read_file("large.txt")
    lines_read = content.splitlines()
    assert len(lines_read) > 0


def test_read_file_truncation_default(mock_codebase):
    """Test default truncation behavior."""
    lines = [f"Line {i}" for i in range(1, 2501)]
    test_file = mock_codebase / "large.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    content = git_ops.read_file("large.txt")

    assert "Line 2000" in content
    assert "Line 2001" not in content
    assert "Truncated." in content
    assert "Read limit is 2000 lines" in content


def test_read_file_pagination(mock_codebase):
    """Test pagination (start_line and end_line)."""
    lines = [f"Line {i}" for i in range(1, 101)]
    test_file = mock_codebase / "pagination.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Request lines 10-20
    content = git_ops.read_file("pagination.txt", start_line=10, end_line=20)

    assert "Line 9" not in content
    assert "Line 10" in content
    assert "Line 20" in content
    assert "Line 21" not in content

    split_lines = content.splitlines()
    assert len(split_lines) == 11  # 10 to 20 inclusive is 11 lines


def test_read_file_start_line_only(mock_codebase):
    """Test using only start_line."""
    lines = [f"Line {i}" for i in range(1, 101)]
    test_file = mock_codebase / "start.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Request lines 90 onwards
    content = git_ops.read_file("start.txt", start_line=90)

    assert "Line 89" not in content
    assert "Line 90" in content
    assert "Line 100" in content


def test_read_file_out_of_bounds(mock_codebase):
    """Test reading out of bounds."""
    lines = ["Line 1", "Line 2"]
    test_file = mock_codebase / "small.txt"
    test_file.write_text("\n".join(lines), encoding="utf-8")

    # Request start_line beyond EOF
    content = git_ops.read_file("small.txt", start_line=10)
    # Should probably be empty or handle gracefully
    assert content.strip() == ""


def test_read_file_not_found(mock_codebase):
    """Test reading a non-existent file."""
    content = git_ops.read_file("nonexistent.txt")
    assert "Error: File nonexistent.txt not found" in content
