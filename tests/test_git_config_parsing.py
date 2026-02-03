import os
import sys
import pytest
from unittest.mock import mock_open

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import git_ops


@pytest.fixture(autouse=True)
def clear_cache():
    git_ops._get_remote_url.cache_clear()
    yield
    git_ops._get_remote_url.cache_clear()


def test_get_remote_url_with_quotes(mocker):
    """Test parsing .git/config with quoted URL."""
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", "/mock")

    config_content = """
[core]
    repositoryformatversion = 0
[remote "origin"]
    url = "https://github.com/user/quoted-repo.git"
    fetch = +refs/heads/*:refs/remotes/origin/*
"""

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data=config_content))
    mocker.patch("subprocess.check_output", side_effect=FileNotFoundError)

    url = git_ops._get_remote_url()
    assert url == "https://github.com/user/quoted-repo.git"


def test_get_remote_url_simple(mocker):
    """Test parsing .git/config with simple URL."""
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", "/mock")

    config_content = """
[remote "origin"]
    url = https://github.com/user/simple-repo.git
"""

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data=config_content))
    mocker.patch("subprocess.check_output", side_effect=FileNotFoundError)

    url = git_ops._get_remote_url()
    assert url == "https://github.com/user/simple-repo.git"


def test_get_remote_url_fallback(mocker):
    """Test fallback to subprocess if config parsing fails."""
    mocker.patch("app.services.git_ops.CODEBASE_ROOT", "/mock")

    # Config exists but no remote origin
    config_content = """
[core]
    repositoryformatversion = 0
"""

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data=config_content))

    # Mock subprocess to return a URL
    mock_subprocess = mocker.patch(
        "subprocess.check_output",
        return_value=b"https://github.com/user/fallback.git\n",
    )

    url = git_ops._get_remote_url()
    assert url == "https://github.com/user/fallback.git"
    mock_subprocess.assert_called_once()
