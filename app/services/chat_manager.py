"""
Service module for managing chat history.
"""

import os
import json
import logging
import uuid

try:
    import fcntl
except ImportError:
    fcntl = None

logger = logging.getLogger(__name__)


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


CHAT_HISTORY_FILE = _get_storage_path("CHAT_HISTORY_FILE", "chat_history.json")
# Size of the chunk to read from end of file to find the closing bracket
SCAN_SIZE = 4096


def load_chat_history():
    """
    Loads chat history from the configured JSON file.
    """
    if not os.path.exists(CHAT_HISTORY_FILE):
        return []
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        # Backfill IDs for messages that lack them
        for msg in history:
            if "id" not in msg:
                msg["id"] = str(uuid.uuid4())

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
    except OSError as e:
        logger.error("Error loading chat history: %s", e)
        return []
    except json.JSONDecodeError as e:
        logger.error("Error decoding chat history: %s", e)
        return []


def save_chat_history(history):
    """
    Saves the provided chat history to the configured JSON file.
    """
    try:
        directory = os.path.dirname(CHAT_HISTORY_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except OSError as e:
        logger.error("Error saving chat history: %s", e)


def _append_optimized(new_message):
    """
    Helper to append message using file seeking to avoid O(N) rewrite.
    Returns True if successful, False if fallback is needed.
    """
    if not (
        os.path.exists(CHAT_HISTORY_FILE) and os.path.getsize(CHAT_HISTORY_FILE) > 0
    ):
        return False

    with open(CHAT_HISTORY_FILE, "r+b") as f:
        if fcntl:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0, os.SEEK_END)
            end_pos = f.tell()

            # Scan backwards for the JSON array closing bracket ']'
            read_size = min(end_pos, SCAN_SIZE)
            f.seek(-read_size, os.SEEK_END)
            tail = f.read(read_size)
            last_bracket_idx = tail.rfind(b"]")

            if last_bracket_idx == -1:
                return False

            # Calculate where the file should be truncated (overwrite ']')
            truncate_pos = end_pos - read_size + last_bracket_idx

            # Determine if the existing list is empty (i.e. "[]")
            # We scan backwards from the closing bracket looking for non-whitespace
            is_empty_array = False
            found_start = False

            # Scan backwards from ']' in the already read 'tail'
            # Start from the character immediately before ']'
            search_idx = last_bracket_idx - 1
            while search_idx >= 0:
                char = tail[search_idx : search_idx + 1]
                if char.strip():
                    # Found a non-whitespace character
                    if char == b"[":
                        is_empty_array = True
                    found_start = True
                    break
                search_idx -= 1

            # If we didn't find the start character in the tail, we can't be sure
            # about the structure (it might be a very long array or weird formatting).
            # Fallback to full rewrite to be safe.
            if not found_start and truncate_pos > 0:
                return False

            f.seek(truncate_pos)
            if not is_empty_array:
                f.write(b",\n")

            # Append new message
            f.write(json.dumps(new_message, indent=2).encode("utf-8"))
            f.write(b"\n]")
            f.truncate()
            return True
        finally:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_UN)


def add_context_marker():
    """Adds a context reset marker to the history."""
    save_message("system", "--- Context Reset ---")


def save_message(role, text, parts=None):
    """
    Appends a message to the chat history and saves it.
    """
    if parts is None:
        parts = [{"text": text}]
    new_message = {"id": str(uuid.uuid4()), "role": role, "parts": parts}

    # Try optimized append
    try:
        # Ensure directory exists
        directory = os.path.dirname(CHAT_HISTORY_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if _append_optimized(new_message):
            return

    except OSError as e:
        logger.warning("Optimized append failed, falling back to full rewrite: %s", e)

    # Fallback to full rewrite
    history = load_chat_history()
    history.append(new_message)
    save_chat_history(history)


def get_history_page(limit=20, offset=0):
    """
    Retrieves a paginated slice of the chat history.
    """
    history = load_chat_history()
    total = len(history)

    # Slice from the end (most recent) backwards
    # offset=0 => end of list
    end_idx = max(total - offset, 0)
    start_idx = max(end_idx - limit, 0)

    messages = history[start_idx:end_idx] if start_idx < end_idx else []

    return {"messages": messages, "has_more": start_idx > 0, "total": total}


def reset_history():
    """
    Deletes the chat history file.
    """
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            os.remove(CHAT_HISTORY_FILE)
            return True
        except OSError as e:
            logger.error("Error deleting chat history: %s", e)
            raise
    return True
