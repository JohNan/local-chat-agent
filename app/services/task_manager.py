"""
Service module for managing Jules tasks persistence.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

_lock = threading.Lock()


def _get_storage_path(env_var_name: str, filename: str) -> str:
    """
    Determines the storage path based on priority:
    1. Environment variable
    2. /config directory (if exists and writable)
    3. Local file (fallback)
    """
    # Priority 1: Environment variable
    env_path = os.environ.get(env_var_name)
    if env_path:
        return env_path

    # Priority 2: /config directory
    config_dir = "/config"
    # Check if /config exists, is a directory, and is writable
    if (
        os.path.exists(config_dir)
        and os.path.isdir(config_dir)
        and os.access(config_dir, os.W_OK)
    ):
        return os.path.join(config_dir, filename)

    # Fallback: Local file
    return filename


TASKS_FILE = _get_storage_path("JULES_TASKS_FILE", "tasks.json")


def _load_tasks_from_file() -> List[Dict]:
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_tasks_to_file(tasks: List[Dict]):
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)


def load_tasks() -> List[Dict]:
    """Returns list of tasks, sorted by created_at desc."""
    with _lock:
        tasks = _load_tasks_from_file()
    # Sort by created_at descending
    tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return tasks


def add_task(task_data: Dict) -> Dict:
    """Appends new task and saves."""
    # Ensure ID and timestamps
    if "id" not in task_data:
        task_data["id"] = str(uuid.uuid4())

    now = datetime.now(timezone.utc).isoformat()
    if "created_at" not in task_data:
        task_data["created_at"] = now
    if "updated_at" not in task_data:
        task_data["updated_at"] = now

    with _lock:
        tasks = _load_tasks_from_file()
        tasks.append(task_data)
        _save_tasks_to_file(tasks)

    return task_data


def update_task_status(session_name: str, new_status: str) -> Optional[Dict]:
    """Updates status by session name."""
    with _lock:
        tasks = _load_tasks_from_file()
        updated_task = None
        for task in tasks:
            if task.get("session_name") == session_name:
                task["status"] = new_status
                task["updated_at"] = datetime.now(timezone.utc).isoformat()
                updated_task = task
                break

        if updated_task:
            _save_tasks_to_file(tasks)

        return updated_task


def get_task_by_session(session_name: str) -> Optional[Dict]:
    """Returns specific task."""
    with _lock:
        tasks = _load_tasks_from_file()
        for task in tasks:
            if task.get("session_name") == session_name:
                return task
    return None
