"""
Service module for managing Jules tasks persistence via SQLite.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Optional

from .database import DatabaseManager


def _row_to_task(row: dict) -> Dict:
    """Helper to convert DB row to task dictionary."""
    task = {
        "id": row["id"],
        "session_name": row["session_name"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
    if row["data"]:
        try:
            extra_data = json.loads(row["data"])
            if isinstance(extra_data, dict):
                task.update(extra_data)
        except json.JSONDecodeError:
            pass
    return task


def load_tasks() -> List[Dict]:
    """Returns list of tasks, sorted by created_at desc."""
    db = DatabaseManager()
    rows = db.fetch_all("SELECT * FROM tasks ORDER BY created_at DESC")
    return [_row_to_task(row) for row in rows]


def add_task(task_data: Dict) -> Dict:
    """Appends new task and saves."""
    if "id" not in task_data:
        task_data["id"] = str(uuid.uuid4())

    now = datetime.now(timezone.utc).isoformat()
    if "created_at" not in task_data:
        task_data["created_at"] = now
    if "updated_at" not in task_data:
        task_data["updated_at"] = now

    # Extract core fields
    task_id = task_data["id"]
    session_name = task_data.get("session_name")
    status = task_data.get("status")
    created_at = task_data["created_at"]
    updated_at = task_data["updated_at"]

    # Everything else goes into data
    extra_data = {
        k: v
        for k, v in task_data.items()
        if k not in ["id", "session_name", "status", "created_at", "updated_at"]
    }

    db = DatabaseManager()
    db.execute_query(
        """
        INSERT INTO tasks (id, session_name, status, created_at, updated_at, data)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (task_id, session_name, status, created_at, updated_at, json.dumps(extra_data)),
    )

    return task_data


def update_task_status(session_name: str, new_status: str) -> Optional[Dict]:
    """Updates status by session name."""
    db = DatabaseManager()

    updated_at = datetime.now(timezone.utc).isoformat()

    cursor = db.execute_query(
        """
        UPDATE tasks
        SET status = ?, updated_at = ?
        WHERE session_name = ?
    """,
        (new_status, updated_at, session_name),
    )

    if cursor.rowcount > 0:
        return get_task_by_session(session_name)

    return None


def get_task_by_session(session_name: str) -> Optional[Dict]:
    """Returns specific task."""
    db = DatabaseManager()
    row = db.fetch_one("SELECT * FROM tasks WHERE session_name = ?", (session_name,))
    if row:
        return _row_to_task(row)
    return None
