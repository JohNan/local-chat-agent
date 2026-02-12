import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    from app.main import app

    return TestClient(app)


@pytest.fixture(name="mock_task_manager")
def fixture_mock_task_manager(mocker):
    """Fixture to mock task_manager."""
    return mocker.patch("app.main.task_manager")


@pytest.fixture(name="mock_jules_api")
def fixture_mock_jules_api(mocker):
    """Fixture to mock jules_api."""
    # We need to mock the functions as AsyncMock because they are awaited
    mock = mocker.patch("app.main.jules_api")
    mock.deploy_to_jules = AsyncMock()
    mock.get_session_status = AsyncMock()
    return mock


@pytest.fixture(name="mock_git_ops")
def fixture_mock_git_ops(mocker):
    """Fixture to mock git_ops."""
    return mocker.patch("app.main.git_ops")


def test_deploy_to_jules_creates_task(
    client, mock_jules_api, mock_task_manager, mock_git_ops
):
    """Test that deploying to Jules creates a task."""
    mock_git_ops.get_repo_info.return_value = {
        "source_id": "test_source",
        "branch": "main",
    }
    mock_jules_api.deploy_to_jules.return_value = {
        "name": "sessions/test-uuid",
        "state": "active",
    }

    response = client.post("/api/deploy_to_jules", json={"prompt": "Refactor code"})

    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify task_manager.add_task was called
    mock_task_manager.add_task.assert_called_once()
    args, _ = mock_task_manager.add_task.call_args
    task_data = args[0]
    assert task_data["session_name"] == "sessions/test-uuid"
    assert "Refactor code" in task_data["prompt_preview"]
    assert task_data["status"] == "pending"


def test_list_tasks(client, mock_task_manager):
    """Test listing tasks."""
    mock_task_manager.load_tasks.return_value = [
        {"id": "1", "session_name": "sessions/1"}
    ]

    response = client.get("/api/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["session_name"] == "sessions/1"


def test_sync_task(client, mock_jules_api, mock_task_manager):
    """Test syncing task status."""
    mock_jules_api.get_session_status.return_value = {
        "name": "sessions/1",
        "state": "SUCCEEDED",
    }
    mock_task_manager.update_task_status.return_value = {
        "session_name": "sessions/1",
        "status": "SUCCEEDED",
    }

    response = client.post("/api/tasks/sessions/1/sync")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCEEDED"

    mock_jules_api.get_session_status.assert_called_with("sessions/1")
    mock_task_manager.update_task_status.assert_called_with("sessions/1", "SUCCEEDED")
