import os
import json
import pytest
from app.services import task_manager


@pytest.fixture
def mock_tasks_file(tmp_path):
    """Fixture to mock the tasks file path."""
    original_file = task_manager.TASKS_FILE
    temp_file = tmp_path / "test_tasks.json"
    task_manager.TASKS_FILE = str(temp_file)
    yield temp_file
    task_manager.TASKS_FILE = original_file


def test_load_tasks_empty(mock_tasks_file):
    """Test loading tasks when file doesn't exist."""
    tasks = task_manager.load_tasks()
    assert tasks == []


def test_add_and_load_task(mock_tasks_file):
    """Test adding a task and then loading it."""
    task_data = {
        "session_name": "session/1",
        "prompt_preview": "test prompt",
        "status": "pending",
    }
    saved_task = task_manager.add_task(task_data)

    assert saved_task["id"] is not None
    assert saved_task["created_at"] is not None
    assert saved_task["updated_at"] is not None
    assert saved_task["status"] == "pending"

    loaded_tasks = task_manager.load_tasks()
    assert len(loaded_tasks) == 1
    assert loaded_tasks[0]["session_name"] == "session/1"


def test_update_task_status(mock_tasks_file):
    """Test updating task status."""
    task_data = {
        "session_name": "session/2",
        "prompt_preview": "test update",
        "status": "pending",
    }
    task_manager.add_task(task_data)

    updated_task = task_manager.update_task_status("session/2", "running")
    assert updated_task is not None
    assert updated_task["status"] == "running"

    loaded_tasks = task_manager.load_tasks()
    assert loaded_tasks[0]["status"] == "running"


def test_get_task_by_session(mock_tasks_file):
    """Test getting a task by session name."""
    task_data = {
        "session_name": "session/3",
        "prompt_preview": "test get",
        "status": "success",
    }
    task_manager.add_task(task_data)

    task = task_manager.get_task_by_session("session/3")
    assert task is not None
    assert task["session_name"] == "session/3"

    missing_task = task_manager.get_task_by_session("session/999")
    assert missing_task is None
