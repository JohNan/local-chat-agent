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

    assert "Error: Access denied. Cannot access path outside of codebase" in result


def test_read_file_security_value_error(mock_codebase, mocker):
    """Test that ValueError in commonpath is handled as access denied."""

    # Mock os.path.commonpath to raise ValueError
    # This simulates a scenario where paths are on different drives on Windows
    mocker.patch("os.path.commonpath", side_effect=ValueError("Test Error"))

    # Even with a seemingly valid path, the ValueError should trigger the access denied
    result = git_ops.read_file("some_file.txt")

    assert "Error: Access denied. Cannot access path outside of codebase" in result


def test_list_files_traversal(mock_codebase):
    """Test that listing files outside the codebase root is blocked."""
    directory = "../"

    # We expect the security check to catch this
    result = git_ops.list_files(directory)

    assert len(result) == 1
    assert "Error: Access denied. Cannot access path outside of codebase" in result[0]


def test_get_file_history_traversal(mock_codebase):
    """Test that getting file history outside the codebase root is blocked."""
    filepath = "../outside_file.txt"

    # We expect the security check to catch this
    result = git_ops.get_file_history(filepath)

    assert "Error: Access denied. Cannot access path outside of codebase" in result


def test_get_definition_traversal(mock_codebase, mocker):
    """Test that getting definition for file outside the codebase root is blocked."""
    filepath = "../outside_file.txt"

    # We expect the security check to catch this before even calling LSP
    # Mocking LSPManager to ensure it's not called if validation fails
    mock_lsp = mocker.patch("app.services.git_ops.LSPManager")

    result = git_ops.get_definition(filepath, 1, 1)

    assert "error" in result
    assert "Access denied" in result["error"]
    mock_lsp.assert_not_called()


def test_get_definition_external_target(mock_codebase, mocker):
    """Test that if definition points to external file, it is blocked."""
    filepath = "some_file.py"

    # Create dummy file inside codebase so input validation passes
    with open(os.path.join(mock_codebase, filepath), "w") as f:
        f.write("content")

    # Mock LSPManager to return a definition outside codebase
    mock_lsp_instance = mocker.MagicMock()
    mocker.patch("app.services.git_ops.LSPManager", return_value=mock_lsp_instance)

    external_path = os.path.abspath(os.path.join(mock_codebase, "../external_lib.py"))
    mock_lsp_instance.get_definition.return_value = {
        "result": [{"uri": f"file://{external_path}", "range": {"start": {"line": 0}}}]
    }

    result = git_ops.get_definition(filepath, 1, 1)

    assert "error" in result
    assert "Access denied. Definition is outside of codebase." in result["error"]
