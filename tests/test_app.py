import pytest
import sys
import os
import json
import subprocess
from unittest.mock import patch, MagicMock

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services import git_ops, chat_manager


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_run(mocker):
    return mocker.patch("app.services.git_ops.subprocess.run")


@pytest.fixture
def mock_check_output(mocker):
    return mocker.patch("app.services.git_ops.subprocess.check_output")


def test_list_files(mocker):
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


def test_git_status(client, mock_check_output):
    # Mock get-url and branch
    mock_check_output.side_effect = [
        b"https://github.com/user/repo.git\n",  # remote url
        b"main\n",  # branch
    ]

    response = client.get("/api/status")
    data = response.get_json()

    assert response.status_code == 200
    assert data["project"] == "user/repo"
    assert data["branch"] == "main"


def test_git_pull_success(client, mock_run):
    # Mock perform_git_pull subprocess.run
    mock_result = MagicMock()
    mock_result.stdout = "Already up to date."
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    response = client.post("/api/git_pull")
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert "Already up to date" in data["output"]

    # Verify subprocess.run was called correctly
    mock_run.assert_called_with(
        ["git", "pull"],
        cwd=git_ops.CODEBASE_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def test_git_pull_failure(client, mock_run):
    # Mock subprocess.run raising CalledProcessError
    # Note: stderr argument was added in Python 3.10+ to CalledProcessError constructor?
    # Actually it's (returncode, cmd, output=None, stderr=None)
    error = subprocess.CalledProcessError(
        1, ["git", "pull"], output="", stderr="Merge conflict"
    )
    mock_run.side_effect = error

    response = client.post("/api/git_pull")
    data = response.get_json()

    assert data["success"] is False
    assert "Merge conflict" in data["output"]


def test_reset(client, mocker):
    mocker.patch("os.path.exists", return_value=True)
    mock_remove = mocker.patch("os.remove")

    response = client.post("/api/reset")
    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "success"
    mock_remove.assert_called_with(chat_manager.CHAT_HISTORY_FILE)
