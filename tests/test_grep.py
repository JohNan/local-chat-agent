"""
Tests for git_ops.grep_code.
"""

import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from app.services import git_ops


@pytest.fixture(name="temp_codebase")
def fixture_temp_codebase():
    """Sets up a temporary codebase for testing."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()

    # Create a dummy file
    with open(os.path.join(temp_dir, "test_file.py"), "w", encoding="utf-8") as f:
        f.write("def target_function():\n    pass\n")

    original_root = git_ops.CODEBASE_ROOT
    git_ops.CODEBASE_ROOT = temp_dir

    yield temp_dir

    # Cleanup
    git_ops.CODEBASE_ROOT = original_root
    shutil.rmtree(temp_dir)


def test_grep_code_basic(temp_codebase):
    """Test grep_code finds a known string."""
    # Ensure fixture is used
    assert os.path.isdir(temp_codebase)

    result = git_ops.grep_code("target_function")
    assert "def target_function" in result
    assert "test_file.py" in result


def test_grep_code_no_matches(temp_codebase):
    """Test grep_code returns 'No matches found.' for a non-existent string."""
    assert os.path.isdir(temp_codebase)

    result = git_ops.grep_code("non_existent_string")
    assert result == "No matches found."


def test_grep_code_case_insensitive(temp_codebase):
    """Test grep_code handles case insensitivity."""
    assert os.path.isdir(temp_codebase)

    # Test 1: Case Insensitive (Default)
    result = git_ops.grep_code("TARGET_FUNCTION", case_sensitive=False)
    assert "def target_function" in result

    # Test 2: Case Sensitive
    result = git_ops.grep_code("TARGET_FUNCTION", case_sensitive=True)
    assert result == "No matches found."


def test_grep_code_truncation(temp_codebase):
    """Test grep_code truncates output."""
    assert os.path.isdir(temp_codebase)

    long_output = "a" * 2005

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = long_output
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = git_ops.grep_code("foo")

        assert len(result) <= 2100
        assert "... [Output truncated to 2000 chars]" in result


def test_grep_code_fallback_commands():
    """Test grep_code fallback to standard grep when not in a git repo."""
    # Mock os.path.exists to simulate no .git directory
    with patch(
        "app.services.git_ops.os.path.exists", return_value=False
    ) as mock_exists, patch("app.services.git_ops.subprocess.run") as mock_run:

        # Configure mock_run result
        mock_result = MagicMock()
        mock_result.stdout = "matches"
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        # Test 1: Default (Case Insensitive)
        git_ops.grep_code("test_query")

        # Verify call arguments for default (case insensitive) fallback
        mock_run.assert_called_with(
            ["grep", "-r", "-n", "-i", "-e", "test_query", "."],
            cwd=git_ops.CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        # Test 2: Case Sensitive
        git_ops.grep_code("test_query", case_sensitive=True)

        # Verify call arguments for case sensitive fallback
        mock_run.assert_called_with(
            ["grep", "-r", "-n", "-e", "test_query", "."],
            cwd=git_ops.CODEBASE_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
