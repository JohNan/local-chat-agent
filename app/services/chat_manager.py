"""
Service module for managing chat history.
"""

import os
import json
import logging

try:
    import fcntl
except ImportError:
    fcntl = None

logger = logging.getLogger(__name__)

CHAT_HISTORY_FILE = os.environ.get("CHAT_HISTORY_FILE", "chat_history.json")


def load_chat_history():
    """
    Loads chat history from the configured JSON file.
    """
    if not os.path.exists(CHAT_HISTORY_FILE):
        return []
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)

        # Sanitization: Remove dangling function calls
        if history and history[-1].get("parts"):
            last_parts = history[-1]["parts"]
            if any("function_call" in part for part in last_parts):
                history.pop()
                logger.warning(
                    "Detected incomplete function call in history. "
                    "Removed last message to prevent API error."
                )

        # Sanitization: Remove orphaned function responses at start
        if history and history[0].get("parts"):
            first_parts = history[0]["parts"]
            if any("function_response" in part for part in first_parts):
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


def save_message(role, text):
    """
    Appends a message to the chat history and saves it.
    """
    new_message = {"role": role, "parts": [{"text": text}]}

    # Try optimized append
    try:
        # Ensure directory exists
        directory = os.path.dirname(CHAT_HISTORY_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        if os.path.exists(CHAT_HISTORY_FILE) and os.path.getsize(CHAT_HISTORY_FILE) > 0:
            with open(CHAT_HISTORY_FILE, "r+b") as f:
                if fcntl:
                    fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    f.seek(0, os.SEEK_END)
                    end_pos = f.tell()

                    # Scan backwards for ']'
                    scan_size = min(end_pos, 1024)
                    f.seek(-scan_size, os.SEEK_END)
                    tail = f.read(scan_size)
                    last_bracket_idx = tail.rfind(b"]")

                    if last_bracket_idx != -1:
                        truncate_pos = end_pos - scan_size + last_bracket_idx

                        # Check if array is empty
                        is_empty_array = False
                        found_char = False

                        # Scan backwards from ']' in the already read 'tail'
                        search_idx = last_bracket_idx - 1
                        while search_idx >= 0:
                            char = tail[search_idx : search_idx + 1]
                            if char.strip():
                                found_char = True
                                if char == b"[":
                                    is_empty_array = True
                                break
                            search_idx -= 1

                        # If not found in tail, scan further back if needed
                        if not found_char and truncate_pos > 0:
                            # Fallback to full rewrite if we can't easily determine structure
                            # (e.g. > 1KB of whitespace)
                            raise OSError(
                                "Ambiguous JSON structure for append optimization"
                            )

                        f.seek(truncate_pos)
                        if not is_empty_array:
                            f.write(b",\n")

                        # Append new message
                        f.write(json.dumps(new_message, indent=2).encode("utf-8"))
                        f.write(b"\n]")
                        f.truncate()
                        return
                finally:
                    if fcntl:
                        fcntl.flock(f, fcntl.LOCK_UN)

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
