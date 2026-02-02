"""
FastAPI application for the backend.
"""

import os
import json
import logging
import traceback
import sys

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from google import genai
from google.genai import types

from app.services import git_ops, jules_api, chat_manager

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
# Helper for tool map
TOOL_MAP = {"list_files": git_ops.list_files, "read_file": git_ops.read_file}

SYSTEM_INSTRUCTION = (
    "You are the Technical Lead and Prompt Architect. "
    "You have **READ-ONLY** access to the user's codebase.\n\n"
    "**CRITICAL RULES:**\n"
    "1. **Explore First:** When the user asks a question, "
    "you must **IMMEDIATELY** use `list_files` and `read_file` to investigate. "
    "**NEVER** ask the user for file paths or code snippets. Find them yourself.\n"
    "2. **Read-Only:** You cannot edit, write, or delete files. "
    "If code changes are required, you must describe them or generate a 'Jules Prompt'.\n"
    '3. **Jules Prompt:** When the user asks to "write a prompt", "deploy", '
    'or "create instructions", you must generate a structured block starting with '
    "`## Jules Prompt` containing the specific context and acceptance criteria.\n\n"
    "Note: `read_file` automatically truncates large files. If you need to read the rest, "
    "use the `start_line` parameter."
)

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
    """Formats chat history for Gemini API."""
    formatted_history = []
    # We need to exclude the very last message (current user msg)
    # when initializing history, because send_message(user_msg) will add it again.
    history_for_gemini = history[:-1] if history else []

    for h in history_for_gemini:
        parts = []
        for p in h.get("parts", []):
            if isinstance(p, dict) and "text" in p:
                parts.append(types.Part(text=p["text"]))
            elif isinstance(p, str):
                parts.append(types.Part(text=p))
        formatted_history.append({"role": h["role"], "parts": parts})
    return formatted_history


def _generate_stream(chat_session, user_msg):
    """
    Generates the chat stream and handles tool execution with recursion.
    """
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements, too-many-nested-blocks
    full_response_parts = []
    current_msg = user_msg
    turn = 0

    try:
        while turn < 5:
            turn += 1
            tool_calls = []
            logger.debug("[TURN %d] Sending message to SDK", turn)

            try:
                stream = chat_session.send_message_stream(current_msg)

                for chunk in stream:
                    # Text processing
                    try:
                        if chunk.text:
                            full_response_parts.append(chunk.text)
                            yield f"event: message\ndata: {json.dumps(chunk.text)}\n\n"
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error(
                            "[TURN %d] Error processing chunk text: %s", turn, e
                        )

                    # Tool call processing
                    try:
                        if hasattr(chunk, "parts"):
                            for part in chunk.parts:
                                if part.function_call:
                                    tool_calls.append(part.function_call)
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.error(
                            "[TURN %d] Error processing chunk parts: %s", turn, e
                        )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Turn %d Error: %s", turn, traceback.format_exc())
                yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
                return

            # Decision Point
            if not tool_calls:
                break

            # Execute Tools
            logger.debug("[TURN %d] Executing tools...", turn)
            tool_descriptions = []
            for fc in tool_calls:
                if fc.name == "read_file":
                    tool_descriptions.append(
                        f"Reading file '{fc.args.get('filepath')}'"
                    )
                elif fc.name == "list_files":
                    tool_descriptions.append(
                        f"Listing directory '{fc.args.get('directory')}'"
                    )
                else:
                    tool_descriptions.append(f"Running {fc.name}")

            joined_descriptions = ", ".join(tool_descriptions)
            # STRICT JSON ENCODING prevents newlines from breaking SSE
            tool_status_msg = f"🛠 {joined_descriptions}..."
            yield f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n"

            response_parts = []
            for fc in tool_calls:
                logger.info("Executing tool: %s args=%s", fc.name, fc.args)
                tool_func = TOOL_MAP.get(fc.name)
                result = None
                if tool_func:
                    try:
                        result = tool_func(**fc.args)
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        result = f"Error executing {fc.name}: {e}"
                else:
                    result = f"Error: Tool {fc.name} not found."

                response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": result}
                    )
                )

            # Update State
            current_msg = response_parts

        full_response_text = "".join(full_response_parts)

        # Save model response
        if full_response_text:
            chat_manager.save_message("model", full_response_text)

        yield "event: done\ndata: [DONE]\n\n"

    finally:
        logger.info("Client disconnected or stream finished.")


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
def deploy_to_jules_route(request: DeployRequest):
    """Endpoint to deploy session to Jules."""
    try:
        prompt_text = request.prompt
        if not prompt_text:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No prompt provided"},
            )

        repo_info = git_ops.get_repo_info()
        result = jules_api.deploy_to_jules(prompt_text, repo_info)
        return {"success": True, "result": result}

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500, content={"success": False, "error": str(e)}
        )


@app.post("/chat")
def chat(request: ChatRequest):
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

    chat_session = CLIENT.chats.create(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            tools=[git_ops.list_files, git_ops.read_file],
            system_instruction=SYSTEM_INSTRUCTION,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
        history=formatted_history,
    )

    return StreamingResponse(
        _generate_stream(chat_session, user_msg),
        media_type="text/event-stream",
    )


@app.get("/chat")
def chat_get(message: str = Query(...)):
    """Handles chat messages (GET) for compatibility."""
    if not CLIENT:
        return JSONResponse(
            status_code=500, content={"error": "Gemini client not initialized"}
        )

    chat_manager.save_message("user", message)
    full_history = chat_manager.load_chat_history()
    formatted_history = _format_history(full_history)

    chat_session = CLIENT.chats.create(
        model="gemini-3-pro-preview",
        config=types.GenerateContentConfig(
            tools=[git_ops.list_files, git_ops.read_file],
            system_instruction=SYSTEM_INSTRUCTION,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
        history=formatted_history,
    )

    return StreamingResponse(
        _generate_stream(chat_session, message),
        media_type="text/event-stream",
    )


# Mount static folder
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")),
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
