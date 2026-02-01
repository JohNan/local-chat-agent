import os
import json
import logging

logger = logging.getLogger(__name__)

CHAT_HISTORY_FILE = os.environ.get("CHAT_HISTORY_FILE", "chat_history.json")


def load_chat_history():
    if not os.path.exists(CHAT_HISTORY_FILE):
        return []
    try:
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
        return []


def save_chat_history(history):
    try:
        directory = os.path.dirname(CHAT_HISTORY_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")


def save_message(role, text):
    history = load_chat_history()
    # Ensure structure matches Google GenAI (list of dicts with 'parts')
    history.append({"role": role, "parts": [{"text": text}]})
    save_chat_history(history)


def get_history_page(limit=20, offset=0):
    history = load_chat_history()
    total = len(history)

    # Slice from the end (most recent) backwards
    # offset=0 => end of list
    end_idx = total - offset
    start_idx = end_idx - limit

    # Clamp indices
    if end_idx > total:
        end_idx = total
    if end_idx < 0:
        end_idx = 0
    if start_idx < 0:
        start_idx = 0

    messages = history[start_idx:end_idx] if start_idx < end_idx else []

    return {"messages": messages, "has_more": start_idx > 0, "total": total}


def reset_history():
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            os.remove(CHAT_HISTORY_FILE)
            return True
        except Exception as e:
            logger.error(f"Error deleting chat history: {e}")
            raise
    return True
