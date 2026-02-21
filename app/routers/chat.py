"""
Router for chat related endpoints.
"""

import asyncio
import logging
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from google.genai import types

from app import agent_engine
from app.config import CLIENT, ENABLE_GOOGLE_SEARCH, HISTORY_LIMIT
from app.services import chat_manager, prompt_router
from app.services.llm_service import (
    prepare_messages,
    format_history,
    get_tool_config,
    get_cached_content_config,
    stream_generator,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    model: str = "gemini-3-pro-preview"
    include_web_search: bool | None = None
    media: list[dict] | None = None


async def _get_system_instruction(user_msg: str, enable_search: bool) -> str:
    """Determines the active persona and returns the system instruction."""
    active_persona = await asyncio.to_thread(prompt_router.load_active_persona)
    if not active_persona:
        active_persona = await asyncio.to_thread(
            prompt_router.classify_intent, user_msg
        )
        await asyncio.to_thread(prompt_router.save_active_persona, active_persona)
        logger.info("Classified intent as: %s", active_persona)

    system_instruction = prompt_router.get_system_instruction(active_persona)
    if enable_search:
        system_instruction += (
            "\n\nYou also have access to Google Search to "
            "find real-time documentation and solutions."
        )
    return system_instruction


async def _initialize_chat_session(
    user_msg: str,
    model: str = "gemini-3-pro-preview",
    include_web_search: bool | None = None,
    media: list[dict] | None = None,
    save_model_pref: bool = False,
):
    """
    Initializes a chat session with the given parameters.
    Returns the session and the message content to process (text or list).
    """
    # Construct parts with media if present
    storage_parts, gemini_msg = prepare_messages(user_msg, media)

    # Save user message first
    await asyncio.to_thread(
        chat_manager.save_message, "user", user_msg, parts=storage_parts
    )

    if save_model_pref:
        # Save model preference
        await asyncio.to_thread(chat_manager.save_setting, "default_model", model)

    # Load history including the message we just saved
    formatted_history = await asyncio.to_thread(
        format_history,
        await asyncio.to_thread(chat_manager.load_chat_history, limit=HISTORY_LIMIT),
    )

    # Determine if search is enabled
    enable_search = (
        include_web_search if include_web_search is not None else ENABLE_GOOGLE_SEARCH
    )

    # Get system instruction
    system_instruction = await _get_system_instruction(user_msg, enable_search)

    # Context Caching Logic
    cache_name, history_arg = get_cached_content_config(
        CLIENT, formatted_history, system_instruction, model
    )

    # Configure tools
    tool = get_tool_config(CLIENT, enable_search)

    if cache_name:
        logger.info("Using context cache: %s", cache_name)
        config = types.GenerateContentConfig(
            tools=[tool],
            cached_content=cache_name,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
    else:
        # history_arg is full history in this case
        config = types.GenerateContentConfig(
            tools=[tool],
            system_instruction=system_instruction,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

    # Use native async client
    chat_session = CLIENT.aio.chats.create(
        model=model,
        config=config,
        history=history_arg,
    )

    # Return session and message content (text or gemini parts list)
    return chat_session, gemini_msg if media else user_msg


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


@router.post("/chat")
async def chat(request: ChatRequest):
    """Handles chat messages (POST)."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    chat_session, msg_content = await _initialize_chat_session(
        user_msg=request.message,
        model=request.model,
        include_web_search=request.include_web_search,
        media=request.media,
        save_model_pref=True,
    )

    queue = asyncio.Queue()
    asyncio.create_task(
        agent_engine.run_agent_task(queue, chat_session, msg_content)
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

    # Use default model and settings for GET requests
    chat_session, msg_content = await _initialize_chat_session(
        user_msg=message,
        model="gemini-3-pro-preview",
        save_model_pref=False,
    )

    queue = asyncio.Queue()
    asyncio.create_task(agent_engine.run_agent_task(queue, chat_session, msg_content))

    return StreamingResponse(
        stream_generator(queue),
        media_type="text/event-stream",
    )
