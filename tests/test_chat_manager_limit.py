"""
Tests for load_chat_history limit functionality.
"""

import os
import sys
import json
import uuid
from datetime import datetime, timezone, timedelta
import pytest

# Ensure we can import app from the root
sys.path.append(os.getcwd())

from app.services import chat_manager


def insert_message(db, role, text, created_at):
    msg_id = str(uuid.uuid4())
    parts = [{"text": text}]
    db.execute_query(
        """
        INSERT INTO messages (id, role, content, parts, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (msg_id, role, text, json.dumps(parts), created_at),
    )


def test_load_history_limit(clean_db):
    """
    Test loading history with a limit.
    """
    now = datetime.now(timezone.utc)

    # Insert 30 messages
    for i in range(30):
        # Ensure distinct timestamps
        ts = (now + timedelta(seconds=i)).isoformat()
        insert_message(clean_db, "user", f"Message {i}", ts)

    # Load with limit 20
    history = chat_manager.load_chat_history(limit=20)
    assert len(history) == 20

    # Check that we got the most recent messages (last 20)
    # The messages were inserted in chronological order 0 to 29.
    # So we expect 10 to 29.
    assert history[0]["parts"][0]["text"] == "Message 10"
    assert history[-1]["parts"][0]["text"] == "Message 29"


def test_load_history_no_limit(clean_db):
    """
    Test loading history without a limit.
    """
    now = datetime.now(timezone.utc)
    for i in range(5):
        ts = (now + timedelta(seconds=i)).isoformat()
        insert_message(clean_db, "user", f"Message {i}", ts)

    # Explicitly test without argument
    history = chat_manager.load_chat_history()
    assert len(history) == 5
    assert history[0]["parts"][0]["text"] == "Message 0"
    assert history[-1]["parts"][0]["text"] == "Message 4"
