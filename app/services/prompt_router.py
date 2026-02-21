"""
Prompt Router Service.
Manages sticky personas and intent classification for the agent.
"""

import json
import os
import logging
from pathlib import Path
from app.config import CLIENT

logger = logging.getLogger(__name__)


def load_core_instruction() -> str:
    """
    Loads the system core instruction.
    Prioritizes /config/system_core.md (Docker volume) over app/prompts/system_core.md.
    """
    search_paths = [
        Path("/config/system_core.md"),
        Path("app/prompts/system_core.md"),
    ]

    for path in search_paths:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to read system core from %s: %s", path, e)

    logger.error("System core instruction not found in any location.")
    return "Error: System core instruction not found."


CORE_INSTRUCTION = load_core_instruction()

PERSONA_PROMPTS = {
    "UI": (
        "Focus on visual consistency, responsiveness, and Material Design. "
        "Includes Rule 7 (Visualizing Compose UI)."
    ),
    "MOBILE": (
        "Focus on Android best practices, lifecycle, and permissions. "
        "Includes Rule 8 (Android Configuration)."
    ),
    "ARCHITECT": "Focus on system design, modularity, and `AGENTS.md` compliance.",
    "CI_CD": "Focus on build stability, Docker, and GitHub Actions.",
    "GENERAL": "",
}

PERSONA_FILE = "storage/persona_state.json"


def load_active_persona() -> str | None:
    """Reads the saved persona key."""
    if not os.path.exists(PERSONA_FILE):
        return None
    try:
        with open(PERSONA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("active_persona")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to load active persona: %s", e)
        return None


def save_active_persona(key: str):
    """Saves the persona key."""
    try:
        os.makedirs(os.path.dirname(PERSONA_FILE), exist_ok=True)
        with open(PERSONA_FILE, "w", encoding="utf-8") as f:
            json.dump({"active_persona": key}, f)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to save active persona: %s", e)


def clear_active_persona():
    """Deletes the state file."""
    if os.path.exists(PERSONA_FILE):
        try:
            os.remove(PERSONA_FILE)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to clear active persona: %s", e)


def classify_intent(user_query: str) -> str:
    """Classifies the user query into a persona category."""
    if not CLIENT:
        return "GENERAL"

    prompt = (
        "Classify this developer query into exactly one category: "
        "[UI, MOBILE, ARCHITECT, CI_CD, GENERAL]. "
        "Return ONLY the category name.\n\n"
        f"Query: {user_query}"
    )

    try:
        response = CLIENT.models.generate_content(
            model="gemini-3-pro-preview",
            contents=prompt,
        )
        category = response.text.strip().upper()
        if category in PERSONA_PROMPTS:
            return category
        return "GENERAL"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to classify intent: %s", e)
        return "GENERAL"


def get_system_instruction(persona_key: str) -> str:
    """Returns the combined system instruction."""
    # Ensure a valid key
    if persona_key not in PERSONA_PROMPTS:
        persona_key = "GENERAL"

    extra_instruction = PERSONA_PROMPTS.get(persona_key, "")
    if extra_instruction:
        return f"{CORE_INSTRUCTION}\n\n{extra_instruction}"
    return CORE_INSTRUCTION
