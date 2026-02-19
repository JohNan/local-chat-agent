"""
Tests for task manager.
"""

# pylint: disable=redefined-outer-name, unused-argument

import pytest
from unittest.mock import patch
from app.services import task_manager


def test_load_tasks_empty():
    """Test loading tasks when DB is empty."""
    tasks = task_manager.load_tasks()
    assert tasks == []


def test_add_and_load_task():
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
    # Check if prompt_preview (extra data) is preserved
    assert loaded_tasks[0]["prompt_preview"] == "test prompt"


def test_update_task_status():
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


def test_get_task_by_session():
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
    assert task["prompt_preview"] == "test get"

    missing_task = task_manager.get_task_by_session("session/999")
    assert missing_task is None
