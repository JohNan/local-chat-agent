"""
FastAPI application for the backend.
"""

import os
import logging
import traceback
import sys
import asyncio

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from google import genai
from google.genai import types

from app.services import git_ops, jules_api, chat_manager
from app import agent_engine

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI()

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

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY environment variable not set.")

# Initialize client
try:
    CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to initialize Gemini client: %s", e)
    CLIENT = None

# --- Models ---


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    message: str


class DeployRequest(BaseModel):
    """Request model for deployment endpoint."""

    prompt: str


# --- Logic ---


def _format_history(history):
    """Formats chat history for Gemini API, ensuring valid roles."""
    formatted_history = []
    # We need to exclude the very last message (current user msg)
    # when initializing history, because send_message(user_msg) will add it again.
    history_for_gemini = history[:-1] if history else []

    for h in history_for_gemini:
        role = h["role"]

        # FIX: Map 'function' role to 'user' to pass SDK validation
        if role == "function":
            role = "user"

        parts = []
        for p in h.get("parts", []):
            if isinstance(p, dict) and "text" in p:
                parts.append(types.Part(text=p["text"]))
            elif isinstance(p, str):
                parts.append(types.Part(text=p))

        formatted_history.append({"role": role, "parts": parts})
    return formatted_history


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
def api_git_pull():
    """Performs a git pull."""
    result = git_ops.perform_git_pull()
    return result


@app.get("/api/history")
def api_history(limit: int = 20, offset: int = 0):
    """Retrieves paginated chat history."""
    result = chat_manager.get_history_page(limit, offset)
    return result


@app.post("/api/reset")
def api_reset():
    """Resets chat history."""
    try:
        chat_manager.reset_history()
        return {"status": "success"}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error resetting history: %s", e)
        return JSONResponse(
            status_code=500, content={"status": "error", "error": str(e)}
        )


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

        repo_info = git_ops.get_repo_info()
        result = await jules_api.deploy_to_jules(prompt_text, repo_info)
        return {"success": True, "result": result}

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@app.post("/chat")
async def chat(request: ChatRequest):
    """Handles chat messages (POST)."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    user_msg = request.message

    # Save user message first
    chat_manager.save_message("user", user_msg)

    # Load history including the message we just saved
    full_history = chat_manager.load_chat_history()
    formatted_history = _format_history(full_history)

    # Use native async client
    chat_session = CLIENT.aio.chats.create(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            tools=[git_ops.list_files, git_ops.read_file],
            system_instruction=agent_engine.SYSTEM_INSTRUCTION,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
        history=formatted_history,
    )

    queue = asyncio.Queue()
    asyncio.create_task(agent_engine.run_agent_task(queue, chat_session, user_msg))

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

    chat_manager.save_message("user", message)
    full_history = chat_manager.load_chat_history()
    formatted_history = _format_history(full_history)

    # Use native async client
    chat_session = CLIENT.aio.chats.create(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            tools=[git_ops.list_files, git_ops.read_file],
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
