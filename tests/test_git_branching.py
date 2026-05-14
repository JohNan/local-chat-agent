"""Tests for Git branching operations."""

from unittest.mock import patch, MagicMock
import pytest
from app.services import git_ops
from app.routers import system


@pytest.fixture
def mock_subprocess_run():  # pylint: disable=redefined-outer-name
    """Mock subprocess.run."""
    with patch("app.services.git_ops.subprocess.run") as mock:
        yield mock


def test_get_branches(mock_subprocess_run):  # pylint: disable=redefined-outer-name
    """Test getting git branches."""
    mock_subprocess_run.return_value = MagicMock(
        stdout="main\nfeature-test\n", returncode=0
    )
    branches = git_ops.get_branches()
    assert branches == ["main", "feature-test"]
    mock_subprocess_run.assert_called_once()


def test_switch_branch_success(
    mock_subprocess_run,
):  # pylint: disable=redefined-outer-name
    """Test successful branch switch."""
    mock_subprocess_run.return_value = MagicMock(
        stdout="Switched to branch 'main'", returncode=0
    )
    result = git_ops.switch_branch("main")
    assert result["success"] is True
    assert "Switched to branch 'main'" in result["output"]


def test_switch_branch_failure(
    mock_subprocess_run,
):  # pylint: disable=redefined-outer-name
    """Test failed branch switch."""
    mock_subprocess_run.side_effect = git_ops.subprocess.CalledProcessError(
        returncode=1,
        cmd="git checkout non-existent",
        stderr="error: pathspec 'non-existent' did not match any file(s) known to git",
    )
    result = git_ops.switch_branch("non-existent")
    assert result["success"] is False
    assert "error" in result["output"]


@pytest.mark.asyncio
async def test_api_get_branches():
    """Test API endpoint for getting branches."""
    with patch("app.services.git_ops.get_branches", return_value=["main", "dev"]):
        response = system.api_get_branches()
        assert response == {"branches": ["main", "dev"]}


@pytest.mark.asyncio
async def test_api_switch_branch():
    """Test API endpoint for switching branches."""
    with patch(
        "app.services.git_ops.switch_branch",
        return_value={"success": True, "output": "ok"},
    ):
        request = system.BranchSwitchRequest(branch_name="dev")
        response = await system.api_switch_branch(request)
        assert response == {"success": True, "output": "ok"}
