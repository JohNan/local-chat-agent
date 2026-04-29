"""
Prompt Router Service.
Manages sticky personas and intent classification for the agent.
"""

import json
import os

import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from pydantic import BaseModel
from google.genai import types
from google.genai import errors

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


def load_cli_core_instruction() -> str:
    """
    Loads the system core instruction for the CLI.
    Prioritizes /config/system_core_cli.md (Docker volume) over app/prompts/system_core_cli.md.
    """
    search_paths = [
        Path("/config/system_core_cli.md"),
        Path("app/prompts/system_core_cli.md"),
    ]

    for path in search_paths:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to read CLI system core from %s: %s", path, e)

    logger.error("CLI System core instruction not found in any location.")
    return "Error: CLI System core instruction not found."


CLI_CORE_INSTRUCTION = load_cli_core_instruction()

ARCHITECT_RULES = (
    "You are a Distinguished Architect, not a developer. "
    "You MUST NOT write executable application code. "
    "Every Final Prompt generated must include a Markdown ADR (Architecture Decision Record) "
    "and a Mermaid.js diagram specific to your domain."
)

PERSONA_PROMPTS = {
    "UI": (
        f"{ARCHITECT_RULES} "
        "Focus on visual consistency, responsiveness, and Material Design. "
        "Includes Rule 7 (Visualizing Compose UI)."
    ),
    "MOBILE": (
        f"{ARCHITECT_RULES} "
        "Focus on Android best practices, lifecycle, and permissions. "
        "Includes Rule 8 (Android Configuration)."
    ),
    "ARCHITECT": f"{ARCHITECT_RULES} "
    "Focus on system design, modularity, and `AGENTS.md` compliance.",
    "CI_CD": f"{ARCHITECT_RULES} "
    "Focus on build stability, Docker, and GitHub Actions.",
    "PLANNER": (
        f"{ARCHITECT_RULES} "
        "Focus on requirements, architecture, and roadmaps. "
        "Use the write_to_docs tool for any documentation. "
        "You have permission to update the `AGENTS.md` and `README.md` "
        "files at the root using the `write_to_docs` tool."
    ),
    "GENERAL": ARCHITECT_RULES,
}

PERSONA_FILE = "storage/persona_state.json"


@lru_cache(maxsize=1)
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
        load_active_persona.cache_clear()
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to save active persona: %s", e)


def clear_active_persona():
    """Deletes the state file."""
    if os.path.exists(PERSONA_FILE):
        try:
            os.remove(PERSONA_FILE)
            load_active_persona.cache_clear()
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Failed to clear active persona: %s", e)


class Intent(BaseModel):
    """Pydantic model for structured intent classification."""

    persona: str
    task_type: str


def classify_intent(user_query: str) -> str:
    """Classifies the user query into a persona category."""
    if not CLIENT:
        return "GENERAL"

    prompt = (
        "Classify this developer query into exactly one category: "
        "[UI, MOBILE, ARCHITECT, CI_CD, PLANNER, GENERAL]. "
        "Also determine the task_type (e.g., 'question', 'feature', 'bug').\n\n"
        "Use PLANNER if the user query contains words like 'plan', 'document', "
        "'architecture', or 'requirements'.\n\n"
        f"Query: {user_query}"
    )

    try:
        response = CLIENT.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Intent,
                temperature=0.0,
            ),
        )
        if response.parsed and isinstance(response.parsed, Intent):
            category = response.parsed.persona.strip().upper()
            if category in PERSONA_PROMPTS:
                return category
        return "GENERAL"
    except errors.APIError as e:
        logger.error("APIError classifying intent: %s", e)
        return "GENERAL"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to classify intent: %s", e)
        return "GENERAL"


def get_system_instruction(persona_key: str, for_cli: bool = False) -> str:
    """Returns the combined system instruction."""
    # Ensure a valid key
    if persona_key not in PERSONA_PROMPTS:
        persona_key = "GENERAL"

    current_date = datetime.now().strftime("%Y-%m-%d")
    date_context = f"Today's date is {current_date}."

    extra_instruction = PERSONA_PROMPTS.get(persona_key, "")

    if for_cli:
        if extra_instruction:
            return f"{date_context}\n\n{CLI_CORE_INSTRUCTION}\n\n{extra_instruction}"
        return f"{date_context}\n\n{CLI_CORE_INSTRUCTION}"

    if extra_instruction:
        return f"{date_context}\n\n{CORE_INSTRUCTION}\n\n{extra_instruction}"
    return f"{date_context}\n\n{CORE_INSTRUCTION}"
