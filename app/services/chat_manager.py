"""
Service module for managing chat history.
"""

import os
import json
import logging

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
                logger.warning("Detected incomplete function call in history. Removed last message to prevent API error.")

        # Sanitization: Remove orphaned function responses at start
        if history and history[0].get("parts"):
            first_parts = history[0]["parts"]
            if any("function_response" in part for part in first_parts):
                history.pop(0)
                logger.warning("Detected orphaned function response in history. Removed first message to prevent API error.")

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
    history = load_chat_history()
    # Ensure structure matches Google GenAI (list of dicts with 'parts')
    history.append({"role": role, "parts": [{"text": text}]})
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
