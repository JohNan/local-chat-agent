"""
Tests for database initialization.
"""

import os
import sys
import sqlite3
import pytest

# Ensure we can import app from the root
sys.path.append(os.getcwd())

from app.services.database import DatabaseManager


def test_init_db_creates_tables(tmp_path):
    """
    Test that init_db creates the necessary tables.
    """
    # Use a temporary database file
    db_path = tmp_path / "test_init_db.db"

    # Reset the singleton instance to ensure a fresh start
    DatabaseManager._instance = None

    # Initialize DatabaseManager with the temporary path
    db = DatabaseManager(db_url=str(db_path))

    # Verify tables do not exist before init_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "tasks" not in tables
        assert "messages" not in tables
        assert "settings" not in tables

    # Initialize the database
    db.init_db()

    # Verify tables exist after init_db
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "tasks" in tables
        assert "messages" in tables
        assert "settings" in tables

        # Verify schema for tasks
        cursor.execute("PRAGMA table_info(tasks)")
        columns = {row[1] for row in cursor.fetchall()}
        expected_tasks_columns = {
            "id",
            "session_name",
            "status",
            "created_at",
            "updated_at",
            "data",
        }
        assert expected_tasks_columns.issubset(columns)

        # Verify schema for messages
        cursor.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cursor.fetchall()}
        expected_messages_columns = {"id", "role", "content", "parts", "created_at"}
        assert expected_messages_columns.issubset(columns)

        # Verify schema for settings
        cursor.execute("PRAGMA table_info(settings)")
        columns = {row[1] for row in cursor.fetchall()}
        expected_settings_columns = {"key", "value"}
        assert expected_settings_columns.issubset(columns)


def test_init_db_idempotency(tmp_path):
    """
    Test that calling init_db multiple times is safe.
    """
    # Use a temporary database file
    db_path = tmp_path / "test_init_db_idempotency.db"

    # Reset the singleton instance
    DatabaseManager._instance = None

    # Initialize DatabaseManager
    db = DatabaseManager(db_url=str(db_path))

    # First initialization
    db.init_db()

    # Second initialization
    try:
        db.init_db()
    except Exception as e:
        pytest.fail(f"Second init_db call raised an exception: {e}")

    # Verify tables still exist and are correct
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "tasks" in tables
        assert "messages" in tables
        assert "settings" in tables
