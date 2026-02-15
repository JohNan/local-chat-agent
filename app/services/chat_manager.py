"""
Service module for managing chat history via SQLite.
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from .database import DatabaseManager

logger = logging.getLogger(__name__)


def _row_to_message(row: dict) -> dict:
    """Helper to convert DB row to message dictionary."""
    msg = {
        "id": row["id"],
        "role": row["role"],
        "created_at": row["created_at"],
    }
    if row["parts"]:
        try:
            msg["parts"] = json.loads(row["parts"])
        except json.JSONDecodeError:
            msg["parts"] = []
    else:
        # Fallback if no parts, use content if available
        if row["content"]:
            msg["parts"] = [{"text": row["content"]}]
        else:
            msg["parts"] = []
    return msg


def load_chat_history():
    """
    Loads full chat history from the database.
    """
    db = DatabaseManager()
    rows = db.fetch_all("SELECT * FROM messages ORDER BY created_at ASC")
    history = [_row_to_message(row) for row in rows]

    # Sanitization: Remove dangling function calls
    if history and history[-1].get("parts"):
        last_parts = history[-1]["parts"]
        if any(
            "function_call" in part or "functionCall" in part for part in last_parts
        ):
            history.pop()
            logger.warning(
                "Detected incomplete function call in history. "
                "Removed last message to prevent API error."
            )

    # Sanitization: Remove orphaned function responses at start
    if history and history[0].get("parts"):
        first_parts = history[0]["parts"]
        if any(
            "function_response" in part or "functionResponse" in part
            for part in first_parts
        ):
            history.pop(0)
            logger.warning(
                "Detected orphaned function response in history. "
                "Removed first message to prevent API error."
            )

    return history


def add_context_marker():
    """Adds a context reset marker to the history."""
    save_message("system", "--- Context Reset ---")


def save_message(role, text, parts=None):
    """
    Appends a message to the chat history and saves it.
    """
    if parts is None:
        parts = [{"text": text}]

    msg_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    # Extract text content if possible
    content = text

    db = DatabaseManager()
    db.execute_query(
        """
        INSERT INTO messages (id, role, content, parts, created_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (msg_id, role, content, json.dumps(parts), created_at),
    )


def get_history_page(limit=20, offset=0):
    """
    Retrieves a paginated slice of the chat history.
    """
    db = DatabaseManager()

    # Get total count
    count_row = db.fetch_one("SELECT COUNT(*) as count FROM messages")
    total = count_row["count"] if count_row else 0

    # Get slice
    rows = db.fetch_all(
        """
        SELECT * FROM messages
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """,
        (limit, offset),
    )

    messages = [_row_to_message(row) for row in rows]
    messages.reverse()  # Restore chronological order

    # has_more is true if total > offset + limit
    has_more = total > (offset + limit)

    return {"messages": messages, "has_more": has_more, "total": total}


def reset_history():
    """
    Deletes the chat history.
    """
    db = DatabaseManager()
    db.execute_query("DELETE FROM messages")
    return True
