"""
FastAPI application for the backend.
"""

import os
import logging
import traceback
import sys
import asyncio
import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from google import genai
from google.genai import types

from app.services import git_ops, jules_api, chat_manager, rag_manager, task_manager
from app import agent_engine

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Lifespan context manager for the FastAPI app."""
    # Startup
    logger.info("Starting background RAG indexing...")
    asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))
    yield
    # Shutdown (if needed)


app = FastAPI(lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
ENABLE_GOOGLE_SEARCH = os.environ.get("ENABLE_GOOGLE_SEARCH", "false").lower() in (
    "true",
    "1",
    "yes",
)

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY environment variable not set.")

# Initialize client
try:
    CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to initialize Gemini client: %s", e)
    CLIENT = None

# Global cache state
CACHE_STATE = {}

# --- Models ---


class MediaItem(BaseModel):
    """Model for media items (e.g. images)."""

    mime_type: str
    data: str


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str
    model: str = "gemini-3-pro-preview"
    include_web_search: bool | None = None
    media: list[MediaItem] | None = None


class DeployRequest(BaseModel):
    """Request model for deployment endpoint."""

    prompt: str


# --- Logic ---


def _format_history(history):
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
                        types.Part.from_bytes(
                            data=base64.b64decode(p["inline_data"]["data"]),
                            mime_type=p["inline_data"]["mime_type"],
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


# --- Routes ---


@app.get("/api/status")
def api_status():
    """Returns repository status."""
    info = git_ops.get_repo_info()
    return info


@app.post("/api/git_pull")
async def api_git_pull():
    """Performs a git pull."""
    result = await asyncio.to_thread(git_ops.perform_git_pull)

    if result.get("success"):
        logger.info("Git pull successful. Triggering background re-indexing...")
        asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))

    return result


@app.get("/api/history")
def api_history(limit: int = 20, offset: int = 0):
    """Retrieves paginated chat history."""
    result = chat_manager.get_history_page(limit, offset)
    return result


@app.post("/api/context_reset")
def api_context_reset():
    """Inserts a context reset marker."""
    try:
        chat_manager.add_context_marker()
        CACHE_STATE.clear()  # Invalidate cache
        return {"status": "success"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error adding context marker: %s", e)
        return JSONResponse(
            status_code=500, content={"status": "error", "error": str(e)}
        )


@app.post("/api/reset")
def api_reset():
    """Resets chat history."""
    try:
        chat_manager.reset_history()
        CACHE_STATE.clear()  # Invalidate cache
        return {"status": "success"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error resetting history: %s", e)
        return JSONResponse(
            status_code=500, content={"status": "error", "error": str(e)}
        )


@app.post("/api/stop")
def api_stop():
    """Stops the current generation task."""
    if agent_engine.cancel_current_task():
        return {"status": "stopped"}
    return {"status": "no_active_task"}


@app.get("/api/stream/active")
async def stream_active():
    """Returns the active stream if one exists."""
    queue = agent_engine.get_active_stream_queue()
    if queue:
        return StreamingResponse(
            stream_generator(queue),
            media_type="text/event-stream",
        )
    return JSONResponse(status_code=404, content={"active": False})


@app.get("/chat/status")
def chat_status():
    """Returns the status of the current task."""
    # Check if there is an active task state
    is_active = agent_engine.CURRENT_STATE is not None
    return {"active": is_active}


@app.get("/chat/stream_active")
async def chat_stream_active():
    """Returns the active stream if one exists (chat path)."""
    return await stream_active()


@app.post("/rag/reindex")
async def rag_reindex():
    """Triggers a codebase re-index."""
    # Run in background
    asyncio.create_task(asyncio.to_thread(rag_manager.index_codebase_task))
    return {"status": "indexing started"}


@app.get("/api/models")
def api_models():
    """Returns a list of available Gemini models."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )
    try:
        models = []
        for m in CLIENT.models.list():
            if "generateContent" in m.supported_actions and m.name.startswith(
                "models/gemini-"
            ):
                # Strip "models/" prefix
                model_name = m.name.replace("models/", "")
                models.append(model_name)
        return {"models": models}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to fetch models: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/deploy_to_jules")
async def deploy_to_jules_route(request: DeployRequest):
    """Endpoint to deploy session to Jules."""
    try:
        prompt_text = request.prompt
        if not prompt_text:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No prompt provided"},
            )

        repo_info = await asyncio.to_thread(git_ops.get_repo_info)
        result = await jules_api.deploy_to_jules(prompt_text, repo_info)

        # Save task
        if result and "name" in result:
            task_data = {
                "session_name": result["name"],
                "prompt_preview": prompt_text[:50]
                + ("..." if len(prompt_text) > 50 else ""),
                "status": "pending",  # Initial status
            }
            await asyncio.to_thread(task_manager.add_task, task_data)

        return {"success": True, "result": result}

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@app.get("/api/tasks")
def api_tasks():
    """Returns list of tasks."""
    return task_manager.load_tasks()


@app.post("/api/tasks/{session_name:path}/sync")
async def api_tasks_sync(session_name: str):
    """Syncs status with Jules API."""
    try:
        status_result = await jules_api.get_session_status(session_name)
        new_status = status_result.get("state", "unknown")
        updated_task = await asyncio.to_thread(
            task_manager.update_task_status, session_name, new_status
        )
        return updated_task
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to sync task: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/jules_session/{session_name:path}")
async def get_jules_session_status(session_name: str):
    """Retrieves the status of a Jules session."""
    try:
        result = await jules_api.get_session_status(session_name)
        return result
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@app.post("/chat")
async def chat(request: ChatRequest):
    """Handles chat messages (POST)."""
    # pylint: disable=too-many-locals
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    user_msg_content = request.message

    # Handle media
    history_parts = []
    gemini_parts = []

    if request.media:
        for media_item in request.media:
            # 1. For history persistence (base64 string)
            history_parts.append(
                {
                    "inline_data": {
                        "mime_type": media_item.mime_type,
                        "data": media_item.data,
                    }
                }
            )
            # 2. For Gemini API (decoded bytes)
            gemini_parts.append(
                types.Part.from_bytes(
                    data=base64.b64decode(media_item.data),
                    mime_type=media_item.mime_type,
                )
            )

    # Add text part
    if request.message:
        # History format uses simple structure or parts list
        # If we have media, we MUST use parts list for consistency in this message
        history_parts.append({"text": request.message})
        gemini_parts.append(types.Part(text=request.message))

    # Save user message first
    # If media is present, use the complex parts structure.
    # Otherwise fallback to simple text saving (handled by chat_manager logic,
    # but we can explicitly pass parts).
    await asyncio.to_thread(
        chat_manager.save_message, "user", user_msg_content, parts=history_parts
    )

    # Load history including the message we just saved
    full_history = await asyncio.to_thread(chat_manager.load_chat_history)
    formatted_history = await asyncio.to_thread(_format_history, full_history)

    # Determine if search is enabled
    if request.include_web_search is not None:
        enable_search = request.include_web_search
    else:
        enable_search = ENABLE_GOOGLE_SEARCH

    # Configure tools
    function_declarations = [
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.list_files
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.read_file
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.get_file_history
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.get_recent_commits
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.grep_code
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.get_file_outline
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=git_ops.read_android_manifest
        ),
        types.FunctionDeclaration.from_callable(
            client=CLIENT, callable=rag_manager.retrieve_context
        ),
    ]

    google_search_tool = types.GoogleSearch() if enable_search else None

    # Construct tool list
    tool = types.Tool(
        function_declarations=function_declarations,
        google_search=google_search_tool,
        code_execution=types.ToolCodeExecution(),
    )

    # Configure system instruction
    system_instruction = agent_engine.SYSTEM_INSTRUCTION
    if enable_search:
        system_instruction += (
            "\n\nYou also have access to Google Search to "
            "find real-time documentation and solutions."
        )

    # Context Caching Logic
    cache_name, history_arg = get_cached_content_config(
        CLIENT, formatted_history, system_instruction, request.model
    )

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
        model=request.model,
        config=config,
        history=history_arg,
    )

    # If we have media, user_msg for agent_task should be the list of parts.
    # Otherwise it can be the string (or list of parts, agent_engine handles both).
    task_input = gemini_parts if request.media else user_msg_content

    queue = asyncio.Queue()
    asyncio.create_task(agent_engine.run_agent_task(queue, chat_session, task_input))

    return StreamingResponse(
        stream_generator(queue),
        media_type="text/event-stream",
    )


@app.get("/chat")
async def chat_get(message: str = Query(...)):
    """Handles chat messages (GET) for compatibility."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    await asyncio.to_thread(chat_manager.save_message, "user", message)
    full_history = await asyncio.to_thread(chat_manager.load_chat_history)
    formatted_history = await asyncio.to_thread(_format_history, full_history)

    # Use native async client
    chat_session = CLIENT.aio.chats.create(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.list_files
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.read_file
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.get_file_history
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.get_recent_commits
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.grep_code
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.get_file_outline
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=git_ops.read_android_manifest
                        ),
                        types.FunctionDeclaration.from_callable(
                            client=CLIENT, callable=rag_manager.retrieve_context
                        ),
                    ],
                    google_search=types.GoogleSearch(),
                    code_execution=types.ToolCodeExecution(),
                )
            ],
            system_instruction=agent_engine.SYSTEM_INSTRUCTION,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
        history=formatted_history,
    )

    queue = asyncio.Queue()
    asyncio.create_task(agent_engine.run_agent_task(queue, chat_session, message))

    return StreamingResponse(
        stream_generator(queue),
        media_type="text/event-stream",
    )


# Mount static folder
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount(
    "/static",
    StaticFiles(directory=static_dir),
    name="static",
)


@app.get("/")
def index():
    """Renders the main page."""
    # Serve index.html from static/dist
    index_path = os.path.join(os.path.dirname(__file__), "static/dist/index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend not found"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5000)
