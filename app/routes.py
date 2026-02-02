"""
Flask routes and API endpoints for the application.
"""

import os
import json
import logging
import traceback
from flask import (
    Blueprint,
    request,
    jsonify,
    render_template,
    stream_with_context,
    Response,
)
from google import genai
from google.genai import types

from app.services import git_ops, jules_api, chat_manager

bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

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
    "`## Jules Prompt` containing the specific context and acceptance criteria."
)

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY environment variable not set.")

# Initialize client (lazy or global)
try:
    CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to initialize Gemini client: %s", e)
    CLIENT = None


@bp.route("/")
def index():
    """Renders the main page."""
    return render_template("index.html")


@bp.route("/api/status", methods=["GET"])
def api_status():
    """Returns repository status."""
    info = git_ops.get_repo_info()
    return jsonify({"project": info["project"], "branch": info["branch"]})


@bp.route("/api/git_pull", methods=["POST"])
def api_git_pull():
    """Performs a git pull."""
    result = git_ops.perform_git_pull()
    return jsonify(result)


@bp.route("/api/history", methods=["GET"])
def api_history():
    """Retrieves paginated chat history."""
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "Invalid limit or offset"}), 400

    result = chat_manager.get_history_page(limit, offset)
    return jsonify(result)


@bp.route("/api/reset", methods=["POST"])
def api_reset():
    """Resets chat history."""
    try:
        chat_manager.reset_history()
        return jsonify({"status": "success"})
    except Exception as e:  # pylint: disable=broad-exception-caught
        return jsonify({"status": "error", "error": str(e)}), 500


@bp.route("/api/deploy_to_jules", methods=["POST"])
def deploy_to_jules_route():
    """Endpoint to deploy session to Jules."""
    try:
        data = request.json
        prompt_text = data.get("prompt")

        if not prompt_text:
            return jsonify({"success": False, "error": "No prompt provided"}), 400

        repo_info = git_ops.get_repo_info()
        result = jules_api.deploy_to_jules(prompt_text, repo_info)

        return jsonify({"success": True, "result": result})

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


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
    full_response_text = ""
    current_msg = user_msg
    turn = 0

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
                        full_response_text += chunk.text
                        yield f"event: message\ndata: {json.dumps(chunk.text)}\n\n"
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("[TURN %d] Error processing chunk text: %s", turn, e)

                # Tool call processing
                try:
                    if hasattr(chunk, "parts"):
                        for part in chunk.parts:
                            if part.function_call:
                                tool_calls.append(part.function_call)
                except Exception as e:  # pylint: disable=broad-exception-caught
                    logger.error("[TURN %d] Error processing chunk parts: %s", turn, e)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Turn %d Error: %s", turn, traceback.format_exc())
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
            return

        # Decision Point
        if not tool_calls:
            break

        # Execute Tools
        logger.debug("[TURN %d] Executing tools...", turn)
        yield f"event: tool\ndata: 🛠 Processing {len(tool_calls)} actions...\n\n"

        response_parts = []
        for fc in tool_calls:
            logger.info("Executing tool: %s", fc.name)
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

    # Save model response
    if full_response_text:
        chat_manager.save_message("model", full_response_text)

    yield "event: done\ndata: [DONE]\n\n"


@bp.route("/chat", methods=["GET", "POST"])
def chat():
    """Handles chat messages."""
    if not CLIENT:
        return jsonify({"error": "Gemini client not initialized"}), 500

    if request.method == "POST":
        data = request.json
        user_msg = data.get("message")
    else:
        user_msg = request.args.get("message")

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

    return Response(
        stream_with_context(_generate_stream(chat_session, user_msg)),
        mimetype="text/event-stream",
    )
