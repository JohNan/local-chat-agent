"""
Security tests for read_file functionality.
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


def test_read_file_path_traversal(mock_codebase):
    """Test that path traversal attempts are blocked."""
    # Attempt to read a file outside the codebase root
    # Using '..' to traverse up the directory tree
    filepath = "../outside_file.txt"

    # We expect the security check to catch this
    result = git_ops.read_file(filepath)

    assert "Error: Access denied. Cannot read outside of codebase." in result


def test_read_file_security_value_error(mock_codebase, mocker):
    """Test that ValueError in commonpath is handled as access denied."""

    # Mock os.path.commonpath to raise ValueError
    # This simulates a scenario where paths are on different drives on Windows
    mocker.patch("os.path.commonpath", side_effect=ValueError("Test Error"))

    # Even with a seemingly valid path, the ValueError should trigger the access denied
    result = git_ops.read_file("some_file.txt")

    assert "Error: Access denied. Cannot read outside of codebase." in result
