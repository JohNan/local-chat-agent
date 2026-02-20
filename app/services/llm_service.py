"""
Service for LLM interactions and helper functions.
"""

import base64
import logging
import asyncio
from google.genai import types

from app.services import git_ops, rag_manager

logger = logging.getLogger(__name__)

# Global cache state
CACHE_STATE = {}

# Global MCP State
MCP_SESSIONS = {}
MCP_TOOL_DEFINITIONS = []
MCP_TOOL_TO_SESSION_MAP = {}


def clear_cache():
    """Clears the global cache state."""
    CACHE_STATE.clear()


def get_tool_config(client, enable_search):
    """Configures tools for the agent."""
    function_declarations = [
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.list_files
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.read_file
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_file_history
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_recent_commits
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.grep_code
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_file_outline
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.read_android_manifest
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_definition
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=rag_manager.search_codebase_semantic
        ),
    ]

    # Append MCP tools
    function_declarations.extend(MCP_TOOL_DEFINITIONS)

    google_search_tool = types.GoogleSearch() if enable_search else None

    return types.Tool(
        function_declarations=function_declarations,
        google_search=google_search_tool,
        code_execution=types.ToolCodeExecution(),
    )


def prepare_messages(user_msg, media):
    """
    Prepares messages for storage and Gemini API.
    Splits media into inline data for JSON storage and Blob objects for the SDK.
    """
    storage_parts = []
    gemini_msg = []

    if user_msg:
        storage_parts.append({"text": user_msg})
        gemini_msg.append(types.Part(text=user_msg))

    if media:
        for item in media:
            # For JSON storage
            storage_parts.append(
                {"inline_data": {"mime_type": item["mime_type"], "data": item["data"]}}
            )
            # For Gemini API
            gemini_msg.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type=item["mime_type"],
                        data=base64.b64decode(item["data"]),
                    )
                )
            )
    return storage_parts, gemini_msg


def format_history(history):
    """Formats chat history for Gemini API, ensuring valid roles."""
    # Find last system message index
    start_index = 0
    for i, msg in enumerate(history):
        if msg.get("role") == "system":
            start_index = i + 1

    # Slice effective history
    history_subset = history[start_index:]

    formatted_history = []
    # We need to exclude the very last message (current user msg)
    # when initializing history, because send_message(user_msg) will add it again.
    history_for_gemini = history_subset[:-1] if history_subset else []

    for h in history_for_gemini:
        role = h["role"]

        parts = []
        has_function_response = False
        for p in h.get("parts", []):
            if isinstance(p, dict):
                if "functionResponse" in p:
                    has_function_response = True
                    parts.append(
                        types.Part.from_function_response(
                            name=p["functionResponse"]["name"],
                            response=p["functionResponse"]["response"],
                        )
                    )
                elif "functionCall" in p:
                    parts.append(
                        types.Part.from_function_call(
                            name=p["functionCall"]["name"],
                            args=p["functionCall"]["args"],
                        )
                    )
                elif "text" in p:
                    parts.append(types.Part(text=p["text"]))
                elif "inline_data" in p:
                    parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=p["inline_data"]["mime_type"],
                                data=base64.b64decode(p["inline_data"]["data"]),
                            )
                        )
                    )
            elif isinstance(p, str):
                parts.append(types.Part(text=p))

        # Map 'function' role to 'user' ONLY for legacy text-based function messages
        if role == "function" and not has_function_response:
            role = "user"

        formatted_history.append({"role": role, "parts": parts})
    return formatted_history


def get_cached_content_config(
    client, full_history, system_instruction, model, ttl_minutes=60
):
    """
    Gets or creates a cache for the chat history, enabling reuse.
    Context caching is only available for input token counts >= 32,768.
    Returns: (cache_name, history_delta)
    """
    global CACHE_STATE  # pylint: disable=global-statement

    sys_hash = str(hash(system_instruction))

    # 1. Attempt Reuse
    if CACHE_STATE:
        cached_count = CACHE_STATE.get("message_count", 0)
        cached_sys_hash = CACHE_STATE.get("system_instruction_hash")
        cached_content_hash = CACHE_STATE.get("content_hash")

        if cached_sys_hash == sys_hash and len(full_history) >= cached_count:
            prefix = full_history[:cached_count]
            # Verify prefix matches cached content
            if str(hash(str(prefix))) == cached_content_hash:
                delta_history = full_history[cached_count:]
                # Reuse if delta isn't too large (e.g. < 20 messages)
                if len(delta_history) <= 20:
                    return CACHE_STATE["name"], delta_history

    # 2. Check if eligible for new cache
    total_text = str(system_instruction) + str(full_history)
    # Threshold: ~100k chars (approx 25k tokens, safe buffer for 32k requirement)
    if len(total_text) < 100000:
        # Too small, verify if we should clear stale cache
        if CACHE_STATE and len(full_history) < CACHE_STATE.get("message_count", 0):
            CACHE_STATE.clear()
        return None, full_history

    # 3. Create New Cache
    try:
        cache = client.caches.create(
            model=model,
            config=types.CreateCachedContentConfig(
                contents=full_history,
                system_instruction=system_instruction,
                ttl=f"{ttl_minutes * 60}s",
            ),
        )

        CACHE_STATE = {
            "name": cache.name,
            "message_count": len(full_history),
            "content_hash": str(hash(str(full_history))),
            "system_instruction_hash": sys_hash,
        }

        return cache.name, []

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to create context cache: %s", e)
        # Clear state if creation failed to avoid stale state issues?
        # Maybe not necessary, but safer.
        return None, full_history


async def stream_generator(queue: asyncio.Queue):
    """
    Reads from the queue and yields to the client.
    Handles client disconnects gracefully.
    """
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    except GeneratorExit:
        logger.warning(
            "Client disconnected from stream. Worker continues in background."
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Stream generator error: %s", e)
