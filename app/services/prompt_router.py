"""
Prompt Router module.
Handles persona classification and system instruction management.
"""

import json
import logging
import os
from app.config import CLIENT

logger = logging.getLogger(__name__)

PERSONA_FILE = "storage/persona_state.json"

CORE_INSTRUCTION = (
    "Technical Lead Agent\n"
    "You are the Technical Lead and Prompt Architect. "
    "You have **READ-ONLY** access to the user's codebase.\n\n"
    "**CRITICAL RULES:**\n"
    "1. **Explore First:** When the user asks a question, "
    "you must **IMMEDIATELY** use `list_files`, `grep_code`, or `read_file` to investigate. "
    "**NEVER** ask the user for file paths or code snippets. Find them yourself.\n"
    "   - Use `search_codebase_semantic` for high-level questions "
    "(e.g. 'How does auth work?', 'Where is the User model?').\n"
    "2. **Debug with History:** If analyzing a bug or regression, "
    "use `get_file_history` to understand recent changes and intent before suggesting a fix.\n"
    "3. **Read-Only:** You cannot edit, write, or delete files. "
    "If code changes are required, you must describe them or generate a 'Jules Prompt'.\n"
    '4. **Jules Prompt:** When the user asks to "write a prompt", "deploy", '
    'or "create instructions", you must generate a structured block starting with '
    "`## Jules Prompt` containing the specific context and acceptance criteria. "
    "The prompt MUST start with a short text that summarize the task. No longer than "
    "one sentence and should NOT contain any markdown.\n"
    "Every Jules Prompt MUST explicitly instruct the agent to: "
    "'First, first read the `AGENTS.md` file to understand the project architecture "
    "and development rules before starting any implementation.'\n"
    "5. **Visualizing Compose UI:** When analyzing Jetpack Compose code, use `get_file_outline` to "
    "identify `@Composable` functions. Treat the nesting of these function calls "
    "(found via `grep_code`) as the visual component tree.\n"
    "6. **Android Configuration:** Always read `AndroidManifest.xml` first to identify "
    "the application entry point and required permissions.\n"
    "7. **Transparency:** Before executing a tool, you must briefly explain your plan to the user. "
    "For example: 'I will search for the `User` class to understand the schema.' "
    "This keeps the user informed of your reasoning.\n"
    "8. **Self-Correction:** If a tool returns an error (e.g., file not found), "
    "read the error message carefully and try to fix the path or arguments before giving up.\n\n"
    "Note: `read_file` automatically truncates large files. If you need to read the rest, "
    "use the `start_line` parameter.\n\n"
    "You have access to a secure Python sandbox (Code Execution tool). "
    "Use it for complex calculations, data processing, or verifying logic. "
    "However, for reading/writing files in the user's project, "
    "you MUST use the provided local tools (`read_file`, `list_files`, etc.) "
    "as the sandbox is isolated."
)

PERSONA_PROMPTS = {
    "UI": (
        "Focus on visual consistency, responsiveness, and Material Design. "
        "Includes Rule 5 (Visualizing Compose UI)."
    ),
    "MOBILE": (
        "Focus on Android best practices, lifecycle, and permissions. "
        "Includes Rule 6 (Android Configuration)."
    ),
    "ARCHITECT": "Focus on system design, modularity, and `AGENTS.md` compliance.",
    "CI_CD": "Focus on build stability, Docker, and GitHub Actions.",
    "GENERAL": "",
}


def load_active_persona() -> str | None:
    """Reads the saved persona key."""
    if not os.path.exists(PERSONA_FILE):
        return None
    try:
        with open(PERSONA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("active_persona")
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Failed to load persona state: %s", e)
        return None


def save_active_persona(key: str):
    """Saves the persona key."""
    try:
        directory = os.path.dirname(PERSONA_FILE)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        with open(PERSONA_FILE, "w", encoding="utf-8") as f:
            json.dump({"active_persona": key}, f)
    except OSError as e:
        logger.error("Failed to save persona state: %s", e)


def clear_active_persona():
    """Deletes the state file."""
    if os.path.exists(PERSONA_FILE):
        try:
            os.remove(PERSONA_FILE)
        except OSError as e:
            logger.error("Failed to clear persona state: %s", e)


def classify_intent(user_query: str) -> str:
    """Classifies the user intent into one of the personas."""
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
            model="gemini-3-pro-preview", contents=prompt
        )
        category = response.text.strip().upper()
        if category in PERSONA_PROMPTS:
            return category
        return "GENERAL"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error classifying intent: %s", e)
        return "GENERAL"


def get_system_instruction(persona_key: str | None) -> str:
    """Returns the system instruction for the given persona."""
    if not persona_key or persona_key not in PERSONA_PROMPTS:
        return CORE_INSTRUCTION

    persona_specific = PERSONA_PROMPTS.get(persona_key, "")
    if not persona_specific:
        return CORE_INSTRUCTION

    return f"{CORE_INSTRUCTION}\n\n**PERSONA INSTRUCTION ({persona_key}):**\n{persona_specific}"
