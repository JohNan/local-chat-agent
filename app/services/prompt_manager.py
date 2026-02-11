"""
Service for managing saved prompts.
"""

import json
import os
import logging
from threading import Lock

# Configure logging
logger = logging.getLogger(__name__)

PROMPTS_FILE = "prompts.json"
_lock = Lock()


def _ensure_file_exists():
    """Ensures the prompts file exists."""
    if not os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def load_prompts():
    """Loads all saved prompts."""
    _ensure_file_exists()
    try:
        with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error("Error loading prompts: %s", e)
        return []


def save_prompt(content: str):
    """Saves a new prompt if it doesn't already exist."""
    with _lock:
        prompts = load_prompts()
        if content not in prompts:
            prompts.append(content)
            try:
                with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(prompts, f, indent=2)
                return True
            except IOError as e:
                logger.error("Error saving prompt: %s", e)
                return False
        return False  # Duplicate


def delete_prompt(index: int):
    """Deletes a prompt by index."""
    with _lock:
        prompts = load_prompts()
        if 0 <= index < len(prompts):
            prompts.pop(index)
            try:
                with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(prompts, f, indent=2)
                return True
            except IOError as e:
                logger.error("Error deleting prompt: %s", e)
                return False
        return False
