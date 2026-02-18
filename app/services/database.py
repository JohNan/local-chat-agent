"""
Database service for SQLite persistence.
"""

import sqlite3
import json
import os
import logging
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import List, Optional

from .storage import get_storage_path

logger = logging.getLogger(__name__)

DATABASE_URL = get_storage_path("DATABASE_URL", "app.db")


class DatabaseManager:
    """Singleton class to manage SQLite database connections and migrations."""

    _instance = None
    db_path: str  # Type hint for pylint

    def __new__(cls, db_url: Optional[str] = None):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
            if db_url:
                cls._instance.db_path = db_url
            else:
                cls._instance.db_path = DATABASE_URL
        return cls._instance

    def __init__(self, db_url: Optional[str] = None):
        """Initialize the DatabaseManager.

        Args:
            db_url: Optional path to the database file. If provided, it overrides
                    the default configuration. This is primarily used for testing.
        """

    @contextmanager
    def get_connection(self):
        """Yields a SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:  # pylint: disable=broad-exception-caught
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self):
        """Initializes the database schema."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    session_name TEXT,
                    status TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    data TEXT
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    role TEXT,
                    content TEXT,
                    parts TEXT,
                    created_at DATETIME
                )
            """)
            logger.info("Database initialized at %s", self.db_path)

    def migrate_from_json(self):
        """Migrates data from legacy JSON files if tables are empty."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Check if tasks table is empty
            cursor.execute("SELECT COUNT(*) FROM tasks")
            tasks_count = cursor.fetchone()[0]

            # Check if messages table is empty
            cursor.execute("SELECT COUNT(*) FROM messages")
            messages_count = cursor.fetchone()[0]

            if tasks_count == 0:
                self._migrate_tasks(cursor)

            if messages_count == 0:
                self._migrate_chat_history(cursor)

    def _migrate_tasks(self, cursor):
        tasks_file = get_storage_path("JULES_TASKS_FILE", "tasks.json")
        if not os.path.exists(tasks_file):
            return

        try:
            with open(tasks_file, "r", encoding="utf-8") as f:
                tasks = json.load(f)

            logger.info("Migrating %d tasks from %s...", len(tasks), tasks_file)

            for task in tasks:
                task_id = task.get("id", str(uuid.uuid4()))
                session_name = task.get("session_name")
                status = task.get("status")
                created_at = task.get("created_at")
                updated_at = task.get("updated_at")

                # Extract other fields into data
                data = {
                    k: v
                    for k, v in task.items()
                    if k
                    not in [
                        "id",
                        "session_name",
                        "status",
                        "created_at",
                        "updated_at",
                    ]
                }

                cursor.execute(
                    """
                    INSERT INTO tasks (id, session_name, status, created_at, updated_at, data)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        task_id,
                        session_name,
                        status,
                        created_at,
                        updated_at,
                        json.dumps(data),
                    ),
                )

            # Rename legacy file
            os.rename(tasks_file, tasks_file + ".bak")
            logger.info("Tasks migration complete.")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error migrating tasks: %s", e)

    def _migrate_chat_history(self, cursor):
        chat_file = get_storage_path("CHAT_HISTORY_FILE", "chat_history.json")
        if not os.path.exists(chat_file):
            return

        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                history = json.load(f)

            logger.info("Migrating %d messages from %s...", len(history), chat_file)

            # Reuse sanitization logic from chat_manager (simplified here as we iterate)
            # Remove dangling function calls at the end
            if history and history[-1].get("parts"):
                last_parts = history[-1]["parts"]
                if any(
                    "function_call" in part or "functionCall" in part
                    for part in last_parts
                ):
                    history.pop()
                    logger.warning("Removed incomplete function call during migration.")

            # Remove orphaned function responses at start
            if history and history[0].get("parts"):
                first_parts = history[0]["parts"]
                if any(
                    "function_response" in part or "functionResponse" in part
                    for part in first_parts
                ):
                    history.pop(0)
                    logger.warning(
                        "Removed orphaned function response during migration."
                    )

            for msg in history:
                msg_id = msg.get("id", str(uuid.uuid4()))
                role = msg.get("role")
                parts = msg.get("parts", [])

                # Extract content (text) from parts for easier querying if available
                content = ""
                for part in parts:
                    if "text" in part:
                        content += part["text"]

                created_at = datetime.now(timezone.utc).isoformat()

                cursor.execute(
                    """
                    INSERT INTO messages (id, role, content, parts, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (msg_id, role, content, json.dumps(parts), created_at),
                )

            # Rename legacy file
            os.rename(chat_file, chat_file + ".bak")
            logger.info("Chat history migration complete.")

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error migrating chat history: %s", e)

    def execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Executes a query and returns the cursor."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[dict]:
        """Executes a query and returns one row as a dict."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def fetch_all(self, query: str, params: tuple = ()) -> List[dict]:
        """Executes a query and returns all rows as a list of dicts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
