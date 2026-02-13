"""
Integration tests for the FastAPI application.
"""

import sys
import os
import subprocess
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pylint: disable=protected-access
from app.services import git_ops, chat_manager  # pylint: disable=wrong-import-position


@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    from app.main import app  # pylint: disable=import-outside-toplevel

    return TestClient(app)


@pytest.fixture(name="mock_run")
def fixture_mock_run(mocker):
    """Fixture to mock subprocess.run."""
    return mocker.patch("app.services.git_ops.subprocess.run")


@pytest.fixture(name="mock_check_output")
def fixture_mock_check_output(mocker):
    """Fixture to mock subprocess.check_output."""
    return mocker.patch("app.services.git_ops.subprocess.check_output")


def test_list_files(mocker):
    """Test the list_files function."""
    # Mock CODEBASE_ROOT
    mock_codebase = "/mock/codebase"
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", mock_codebase)

    # Mock os.path.exists
    original_exists = os.path.exists

    def mock_exists(path):
        if path.startswith(mock_codebase):
            return True
        return original_exists(path)

    mocker.patch("os.path.exists", side_effect=mock_exists)

    # Mock os.walk
    def mock_walk(path):
        # Normalize path to match mock expectation (remove trailing /.)
        norm_path = os.path.normpath(path)
        if norm_path == mock_codebase:
            # root, dirs, files
            dirs = ["src", ".git"]
            files = ["readme.md"]
            yield (mock_codebase, dirs, files)

            # Simulate os.walk recursion based on modified dirs
            if "src" in dirs:
                yield (os.path.join(mock_codebase, "src"), [], ["main.py"])
            if ".git" in dirs:
                yield (os.path.join(mock_codebase, ".git"), [], ["config"])

    mocker.patch("os.walk", side_effect=mock_walk)

    files = git_ops.list_files(".")

    # Should ignore .git
    assert "readme.md" in files
    assert os.path.join("src", "main.py") in files

    # Should not contain .git stuff
    git_files = [f for f in files if ".git" in f]
    assert len(git_files) == 0


def test_git_status(client, mock_check_output, mocker):
    """Test the /api/status endpoint."""
    # Ensure caches are cleared so we don't get stale data
    git_ops.get_repo_info.cache_clear()
    git_ops._get_remote_url.cache_clear()

    # Mock CODEBASE_ROOT to non-existent path so _get_remote_url
    # fails file lookup and falls back to subprocess
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", "/non/existent/path")

    # Mock get-url and branch
    mock_check_output.side_effect = [
        b"https://github.com/user/repo.git\n",  # remote url
        b"main\n",  # branch
    ]

    response = client.get("/api/status")
    data = response.json()

    assert response.status_code == 200
    assert data["project"] == "user/repo"
    assert data["branch"] == "main"


def test_git_pull_success(client, mock_run):
    """Test successful git pull."""

    # Mock perform_git_pull subprocess.run
    def side_effect(args, **kwargs):
        if args == ["git", "pull"]:
            mock_result = MagicMock()
            mock_result.stdout = "Already up to date."
            mock_result.returncode = 0
            return mock_result
        # Return default mock for other calls (e.g., lsb_release)
        # Ensure stdout/stderr are bytes if text=True isn't set, or str if it is
        default_mock = MagicMock()
        if kwargs.get("text"):
            default_mock.stdout = ""
            default_mock.stderr = ""
        else:
            default_mock.stdout = b""
            default_mock.stderr = b""
        default_mock.returncode = 0
        return default_mock

    mock_run.side_effect = side_effect

    response = client.post("/api/git_pull")
    data = response.json()

    assert response.status_code == 200
    assert data["success"] is True
    assert "Already up to date" in data["output"]

    # Verify subprocess.run was called correctly
    mock_run.assert_any_call(
        ["git", "pull"],
        cwd=git_ops.CODEBASE_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def test_git_pull_failure(client, mock_run):
    """Test failed git pull."""

    # Mock subprocess.run raising CalledProcessError
    def side_effect(args, **kwargs):
        if args == ["git", "pull"]:
            raise subprocess.CalledProcessError(
                1, ["git", "pull"], output="", stderr="Merge conflict"
            )
        # Return default mock for other calls
        default_mock = MagicMock()
        if kwargs.get("text"):
            default_mock.stdout = ""
            default_mock.stderr = ""
        else:
            default_mock.stdout = b""
            default_mock.stderr = b""
        default_mock.returncode = 0
        return default_mock

    mock_run.side_effect = side_effect

    response = client.post("/api/git_pull")
    data = response.json()

    assert data["success"] is False
    assert "Merge conflict" in data["output"]


def test_reset(client, mocker):
    """Test the /api/reset endpoint."""
    mocker.patch("os.path.exists", return_value=True)
    mock_remove = mocker.patch("os.remove")

    response = client.post("/api/reset")
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "success"
    mock_remove.assert_any_call(chat_manager.CHAT_HISTORY_FILE)
