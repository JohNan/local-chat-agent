"""
Router for chat related endpoints.
"""

import asyncio
import logging
from dataclasses import dataclass
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from google.genai import types

from app import agent_engine
from app.config import CLIENT, ENABLE_GOOGLE_SEARCH, HISTORY_LIMIT, LLM_ENGINE
from app.services import chat_manager, prompt_router
from app.services.llm_service import (
    prepare_messages,
    format_history,
    get_tool_config,
    get_cached_content_config,
    stream_generator,
    TurnContext,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class CliApplyRequest(BaseModel):
    """Request model for cli apply endpoint."""
    prompt: str

class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    model: str = "gemini-3-pro-preview"
    include_web_search: bool | None = None
    include_embeddings: bool | None = None
    media: list[dict] | None = None


@dataclass(slots=True)
class ChatSessionSetup:
    """Holds chat session setup data for a request."""

    chat_session: object
    turn_context: TurnContext


def _search_enabled(include_web_search: bool | None) -> bool:
    """Determines whether web search should be enabled."""
    if include_web_search is not None:
        return include_web_search
    return ENABLE_GOOGLE_SEARCH


def _embeddings_enabled(include_embeddings: bool | None) -> bool:
    """Determines whether embeddings should be enabled."""
    if include_embeddings is not None:
        return include_embeddings
    return True


async def _get_system_instruction(
    user_msg: str,
    enable_search: bool,
    _enable_embeddings: bool,  # Kept for signature compatibility if extended later
    classify_if_missing: bool = False,
) -> str:
    """Builds the system instruction for a request."""
    active_persona = await asyncio.to_thread(prompt_router.load_active_persona)
    if not active_persona and classify_if_missing:
        active_persona = await asyncio.to_thread(
            prompt_router.classify_intent, user_msg
        )
        await asyncio.to_thread(prompt_router.save_active_persona, active_persona)
        logger.info("Classified intent as: %s", active_persona)

    system_instruction = prompt_router.get_system_instruction(
        active_persona, for_cli=(LLM_ENGINE == "cli")
    )
    if enable_search:
        system_instruction += (
            "\n\nYou also have access to Google Search to "
            "find real-time documentation and solutions."
        )
    return system_instruction


def _build_generation_config(
    tool: types.Tool, system_instruction: str, cache_name: str | None
) -> types.GenerateContentConfig:
    """Builds the Gemini generation config."""
    base_config = {
        "tools": [tool],
        "automatic_function_calling": types.AutomaticFunctionCallingConfig(
            disable=True
        ),
        "thinking_config": types.ThinkingConfig(
            thinking_level=types.ThinkingLevel.HIGH
        ),
    }
    if cache_name:
        logger.info("Using context cache: %s", cache_name)
        return types.GenerateContentConfig(
            cached_content=cache_name,
            **base_config,
        )
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        **base_config,
    )


async def _create_post_chat_session(
    user_msg: str,
    model: str,
    formatted_history: list[dict],
    enable_search: bool,
    enable_embeddings: bool,
) -> ChatSessionSetup:
    """Creates the chat session and turn context for POST requests."""
    system_instruction = await _get_system_instruction(
        user_msg, enable_search, enable_embeddings, classify_if_missing=True
    )
    cache_name, history_arg = get_cached_content_config(
        CLIENT, formatted_history, system_instruction, model
    )
    turn_context = TurnContext(
        system_instruction=system_instruction,
        is_new_context=len(formatted_history) == 0,
    )
    chat_session = CLIENT.aio.chats.create(
        model=model,
        config=_build_generation_config(
            get_tool_config(CLIENT, enable_search, enable_embeddings),
            system_instruction,
            cache_name,
        ),
        history=history_arg,
    )
    return ChatSessionSetup(chat_session=chat_session, turn_context=turn_context)


@router.post("/api/stop")
def api_stop():
    """Stops the current generation task."""
    if agent_engine.cancel_current_task():
        return {"status": "stopped"}
    return {"status": "no_active_task"}


@router.get("/api/stream/active")
async def stream_active():
    """Returns the active stream if one exists."""
    queue = agent_engine.get_active_stream_queue()
    if queue:
        return StreamingResponse(
            stream_generator(queue),
            media_type="text/event-stream",
        )
    return JSONResponse(status_code=404, content={"active": False})


@router.get("/chat/status")
def chat_status():
    """Returns the status of the current task."""
    # Check if there is an active task state
    is_active = agent_engine.CURRENT_STATE is not None
    return {"active": is_active}


@router.get("/chat/stream_active")
async def chat_stream_active():
    """Returns the active stream if one exists (chat path)."""
    return await stream_active()


@router.post("/api/cli/apply")
async def api_cli_apply(request: CliApplyRequest):
    """Handles autonomous CLI implementation."""
    import os
    from app.config import CLI_SETUP_SCRIPT
    from app.services import llm_service

    setup_script = chat_manager.get_setting("cli_setup_script", CLI_SETUP_SCRIPT)
    if os.path.exists(setup_script):
        logger.info(f"Executing setup script: {setup_script}")
        process = await asyncio.create_subprocess_shell(setup_script)
        await process.wait()

    task_state = agent_engine.TaskState()
    service = llm_service.CLILLMService()

    await service.execute_turn(
        chat_session=None,
        current_msg=request.prompt,
        task_state=task_state,
        turn_context=None,
        mode="implementation"
    )
    return {"success": True}

@router.post("/chat")
async def chat(request: ChatRequest):
    """Handles chat messages (POST)."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    # Construct parts with media if present
    storage_parts, gemini_msg = prepare_messages(request.message, request.media)

    # Save user message first
    await asyncio.to_thread(
        chat_manager.save_message, "user", request.message, parts=storage_parts
    )

    # Save model preference
    await asyncio.to_thread(chat_manager.save_setting, "default_model", request.model)

    # Load history including the message we just saved
    full_history = await asyncio.to_thread(
        chat_manager.load_chat_history, limit=HISTORY_LIMIT
    )
    formatted_history = await asyncio.to_thread(format_history, full_history)
    session_setup = await _create_post_chat_session(
        request.message,
        request.model,
        formatted_history,
        _search_enabled(request.include_web_search),
        _embeddings_enabled(request.include_embeddings),
    )

    queue = asyncio.Queue()
    asyncio.create_task(
        agent_engine.run_agent_task(
            queue,
            session_setup.chat_session,
            gemini_msg if request.media else request.message,
            session_setup.turn_context,
        )
    )

    return StreamingResponse(
        stream_generator(queue),
        media_type="text/event-stream",
    )


@router.get("/chat")
async def chat_get(message: str = Query(...)):
    """Handles chat messages (GET) for compatibility."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    await asyncio.to_thread(chat_manager.save_message, "user", message)
    full_history = await asyncio.to_thread(chat_manager.load_chat_history)
    formatted_history = await asyncio.to_thread(format_history, full_history)
    system_instruction = await _get_system_instruction(
        message, ENABLE_GOOGLE_SEARCH, True
    )
    turn_context = TurnContext(
        system_instruction=system_instruction,
        is_new_context=True,
    )

    chat_session = CLIENT.aio.chats.create(
        model="gemini-3-pro-preview",
        config=_build_generation_config(
            get_tool_config(CLIENT, ENABLE_GOOGLE_SEARCH, True),
            system_instruction,
            None,
        ),
        history=formatted_history,
    )

    queue = asyncio.Queue()
    asyncio.create_task(
        agent_engine.run_agent_task(queue, chat_session, message, turn_context)
    )

    return StreamingResponse(
        stream_generator(queue),
        media_type="text/event-stream",
    )
