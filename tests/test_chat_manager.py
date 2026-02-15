"""
Tests for the chat manager service.
"""

# pylint: disable=wrong-import-position, redefined-outer-name

import json
import os
import sys
import pytest
from unittest.mock import patch
from datetime import datetime, timezone

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import chat_manager
from app.services.database import DatabaseManager


@pytest.fixture
def test_db(tmp_path):
    """Fixture to mock the database."""
    db_path = tmp_path / "test.db"

    # Reset singleton to force re-initialization with new path
    DatabaseManager._instance = None

    with patch("app.services.database.DATABASE_URL", str(db_path)):
        # Initialize DB
        db = DatabaseManager()
        db.init_db()
        yield db

    # Cleanup
    DatabaseManager._instance = None


def insert_message(db, role, parts, created_at=None):
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()

    import uuid

    msg_id = str(uuid.uuid4())
    content = ""  # Simplified

    db.execute_query(
        """
        INSERT INTO messages (id, role, content, parts, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (msg_id, role, content, json.dumps(parts), created_at),
    )


def test_load_history_normal(test_db):
    """
    Test loading a normal history file without any issues.
    """
    insert_message(test_db, "user", [{"text": "Hello"}])
    insert_message(test_db, "model", [{"text": "Hi there"}])

    history = chat_manager.load_chat_history()
    assert len(history) == 2

    # Check content matches and IDs are present
    assert history[0]["role"] == "user"
    assert history[0]["parts"][0]["text"] == "Hello"
    assert "id" in history[0]

    assert history[1]["role"] == "model"
    assert history[1]["parts"][0]["text"] == "Hi there"
    assert "id" in history[1]


def test_load_history_dangling_function_call(test_db, mocker):
    """
    Test that a history ending with a function call is sanitized.
    """
    insert_message(test_db, "user", [{"text": "Do something"}])
    insert_message(test_db, "model", [{"function_call": {"name": "foo", "args": {}}}])

    # Mock logger to verify warning
    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    # Should remove the last message
    assert len(history) == 1
    assert history[0]["role"] == "user"
    mock_logger.warning.assert_called_with(
        "Detected incomplete function call in history. "
        "Removed last message to prevent API error."
    )


def test_load_history_orphaned_function_response(test_db, mocker):
    """
    Test that a history starting with a function response is sanitized.
    """
    insert_message(
        test_db, "function", [{"function_response": {"name": "foo", "response": {}}}]
    )
    insert_message(test_db, "model", [{"text": "Ok"}])

    # Mock logger
    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    assert len(history) == 1
    assert history[0]["role"] == "model"
    # Verify warning if applicable
    mock_logger.warning.assert_called()


def test_load_history_complex_parts(test_db, mocker):
    """
    Test sanitization when function calls are embedded in complex parts.
    """
    # Test with multiple parts where one might be function call
    insert_message(test_db, "user", [{"text": "check this"}])
    insert_message(
        test_db,
        "model",
        [
            {"text": "thinking..."},
            {"function_call": {"name": "foo", "args": {}}},
        ],
    )

    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    assert len(history) == 1
    assert history[0]["role"] == "user"
    mock_logger.warning.assert_called()
