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


def load_persona_prompts() -> dict[str, str]:
    """Loads persona prompts from the filesystem."""
    prompts = {}
    prompts_dir = Path("app/prompts/personas")
    if prompts_dir.exists():
        for file in prompts_dir.glob("*.md"):
            try:
                prompts[file.stem.upper()] = file.read_text(encoding="utf-8")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Failed to read prompt %s: %s", file, e)

    if not prompts:
        prompts = {
            "CHAT": (
                "You are in read-only mode. Explore and explain the codebase, "
                "plan changes, and finish every substantive answer with an ADR "
                "and a final `## Jules Prompt` heading."
            ),
            "CODE": (
                "You are in coding mode with full read-write tools. Implement "
                "changes directly following TDD. Do NOT write Jules Prompts."
            ),
        }
    prompts["GENERAL"] = ARCHITECT_RULES
    return prompts


PERSONA_PROMPTS = load_persona_prompts()

TOP_LEVEL_PERSONAS = {"CHAT", "CODE"}

SPECIALIST_PERSONAS = {  # must equal actual .md stems (uppercased)
    "UI",
    "FRONTEND-DESIGN",
    "MOBILE",
    "ARCHITECT",
    "DEBUG",
    "CI_CD",
    "SIMPLIFY",
    "REVIEW",
    "REVIEW-SECURITY",
    "BRAINSTORM",
}

DEFAULT_TOP_LEVEL = "CHAT"  # safe default = read-only


# Legacy persona keys (from a stale storage/persona_state.json) mapped onto the
# new two-tier top-level personas. Write-ish keys become CODE; advisory /
# ADR-producing keys become CHAT. Unknown keys fall back to CHAT (read-only).
_LEGACY_TO_TOPLEVEL = {
    "CODE": "CODE",
    "DEBUG": "CODE",
    "MOBILE": "CODE",
    "UI": "CODE",
    "FRONTEND-DESIGN": "CODE",
    "CI_CD": "CODE",
    "SIMPLIFY": "CODE",
    "DEFAULT": "CODE",
    "GENERAL": "CODE",
    "ASK": "CHAT",
    "ARCHITECT": "CHAT",
    "PLAN": "CHAT",
    "PLANNER": "CHAT",
    "WRITE-PROMPT": "CHAT",
    "REVIEW": "CHAT",
    "REVIEW-SECURITY": "CHAT",
    "BRAINSTORM": "CHAT",
    "CHAT": "CHAT",
}


# Closing contract appended to every CHAT system instruction so the obligation
# survives even if chat.md is overridden via /config. Mirrors AGENTS.md.
CHAT_OUTPUT_CONTRACT = (
    "## Mandatory Closing Contract\n\n"
    "You are in read-only mode. End every substantive answer with, in this order "
    "and OUTSIDE any `<details>` blocks:\n\n"
    "1. An **ADR** (Architecture Decision Record) with **Context**, **Decision**, "
    "and **Consequences** sections justifying the proposed approach.\n"
    "2. A **Mermaid.js diagram** where relevant, visualizing the data flow or "
    "component interaction.\n"
    "3. A final `## Jules Prompt` heading. This MUST be the LAST heading in your "
    "response. The deployment system extracts everything after the LAST "
    "`## Jules Prompt` heading and strips `<details>` blocks, so keep the ADR and "
    "diagram outside `<details>`. Instruct the agent to read `AGENTS.md` first and "
    "include a one-sentence summary plus actionable requirements and acceptance "
    "criteria. This block can be delegated to Jules or handed off locally to CODE."
)

# CLI-engine-specific guidance for write-capable (CODE) sessions: the Gemini CLI
# policy denies the built-in write_file/replace tools, so the agent must use the
# MCP equivalents. Appended only for CODE + CLI (CHAT has no write tools).
CLI_CODE_TOOL_GUIDANCE = (
    "## Tooling (CLI)\n\n"
    "Implement autonomously: modify files with the provided tools and run tests to "
    "verify your changes, diagnosing and fixing failures yourself. The built-in "
    "`write_file` and `replace` tools are disabled by policy — you MUST use the MCP "
    "tools `write_file_safe` and `replace_safe` instead. If the built-in shell tool "
    "fails for complex redirections, use the MCP-provided `run_shell_command` tool."
)


def normalize_persona(key: str | None) -> str:
    """Maps a (possibly legacy) persona key onto a valid top-level persona."""
    if not key:
        return DEFAULT_TOP_LEVEL
    upper = key.upper()
    if upper in TOP_LEVEL_PERSONAS:
        return upper
    return _LEGACY_TO_TOPLEVEL.get(upper, DEFAULT_TOP_LEVEL)


def is_persona_write_capable(persona: str | None) -> bool:
    """Checks if a persona is allowed to perform write operations. Only CODE writes."""
    return (persona or DEFAULT_TOP_LEVEL).upper() == "CODE"


PERSONA_FILE = "storage/persona_state.json"


@lru_cache(maxsize=1)
def load_active_persona() -> str | None:
    """Reads the saved persona key."""
    if not os.path.exists(PERSONA_FILE):
        return None
    try:
        with open(PERSONA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return normalize_persona(data.get("active_persona"))
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


def classify_specialist(user_query: str) -> str | None:
    """
    Classifies the user query into one of the internal specialist knowledge
    modules. Returns the specialist key (a member of SPECIALIST_PERSONAS) or
    None when no specialist applies or on any API error (graceful: no
    specialist knowledge is appended).
    """
    if not CLIENT:
        return None

    keys_str = ", ".join(sorted(SPECIALIST_PERSONAS))
    prompt = (
        "Classify this developer query into exactly one specialist category: "
        f"[{keys_str}, NONE]. "
        "Choose the single most relevant specialist whose knowledge would help "
        "answer the query. If none of them clearly applies, return NONE.\n\n"
        "Also determine the task_type (e.g., 'question', 'feature', 'bug').\n\n"
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
            if category in SPECIALIST_PERSONAS:
                return category
        return None
    except errors.APIError as e:
        logger.error("APIError classifying specialist: %s", e)
        return None
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to classify specialist: %s", e)
        return None


def get_system_instruction(
    persona_key: str, user_msg: str | None = None, for_cli: bool = False
) -> str:
    """Returns the combined system instruction for a top-level persona."""
    persona_key = normalize_persona(persona_key)

    current_date = datetime.now().strftime("%Y-%m-%d")
    date_context = f"Today's date is {current_date}."

    core = CLI_CORE_INSTRUCTION if for_cli else CORE_INSTRUCTION
    base = PERSONA_PROMPTS.get(persona_key, "")

    parts = [date_context, core]
    if base:
        parts.append(base)

    # Append the most relevant specialist knowledge module, but only when an
    # actual user message is present (the status-poll token-count path passes
    # no message, so it must not trigger an LLM call on every poll).
    if user_msg:
        specialist = classify_specialist(user_msg)
        if specialist:
            specialist_prompt = PERSONA_PROMPTS.get(specialist, "")
            if specialist_prompt:
                parts.append(
                    f"### Specialist Knowledge: {specialist}\n{specialist_prompt}"
                )

    if persona_key == "CHAT":
        parts.append(CHAT_OUTPUT_CONTRACT)
    elif persona_key == "CODE" and for_cli:
        parts.append(CLI_CODE_TOOL_GUIDANCE)

    return "\n\n".join(parts)
