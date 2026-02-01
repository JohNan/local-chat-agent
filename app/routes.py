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

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY environment variable not set.")

# Initialize client (lazy or global)
try:
    client = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    client = None


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/status", methods=["GET"])
def api_status():
    info = git_ops.get_repo_info()
    return jsonify({"project": info["project"], "branch": info["branch"]})


@bp.route("/api/git_pull", methods=["POST"])
def api_git_pull():
    result = git_ops.perform_git_pull()
    return jsonify(result)


@bp.route("/api/history", methods=["GET"])
def api_history():
    try:
        limit = int(request.args.get("limit", 20))
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "Invalid limit or offset"}), 400

    result = chat_manager.get_history_page(limit, offset)
    return jsonify(result)


@bp.route("/api/reset", methods=["POST"])
def api_reset():
    try:
        chat_manager.reset_history()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/api/deploy_to_jules", methods=["POST"])
def deploy_to_jules():
    try:
        data = request.json
        prompt_text = data.get("prompt")

        if not prompt_text:
            return jsonify({"success": False, "error": "No prompt provided"}), 400

        repo_info = git_ops.get_repo_info()
        result = jules_api.deploy_to_jules(prompt_text, repo_info)

        return jsonify({"success": True, "result": result})

    except Exception as e:
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


def generate_response(session, message):
    try:
        response_stream = session.send_message_stream(message)

        for chunk in response_stream:
            if not chunk.candidates:
                continue

            part = chunk.candidates[0].content.parts[0]

            if part.function_call:
                fc = part.function_call
                args_repr = (
                    ", ".join(f"{k}={v!r}" for k, v in fc.args.items())
                    if fc.args
                    else ""
                )

                # Yield tool log
                yield f"event: tool\ndata: 🛠 {fc.name}({args_repr})\n\n"

                # Execute tool
                tool_func = TOOL_MAP.get(fc.name)
                result = None
                if tool_func:
                    try:
                        result = tool_func(**fc.args)
                    except Exception as e:
                        result = f"Error executing {fc.name}: {e}"
                else:
                    result = f"Error: Tool {fc.name} not found."

                # Continue conversation with tool result
                fn_response_part = types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name, response={"result": result}
                    )
                )

                yield from generate_response(session, fn_response_part)
                return

            elif part.text:
                yield f"event: message\ndata: {json.dumps(part.text)}\n\n"

    except Exception as e:
        logger.error(traceback.format_exc())
        yield f"event: error\ndata: {json.dumps(str(e))}\n\n"


@bp.route("/chat", methods=["POST"])
def chat():
    if not client:
        return jsonify({"error": "Gemini client not initialized"}), 500

    data = request.json
    user_msg = data.get("message")

    # Save user message first
    chat_manager.save_message("user", user_msg)

    # Load history including the message we just saved
    full_history = chat_manager.load_chat_history()

    # We need to exclude the very last message (current user msg)
    # when initializing history, because send_message(user_msg) will add it again.
    history_for_gemini = full_history[:-1] if full_history else []

    formatted_history = []
    for h in history_for_gemini:
        parts = []
        for p in h.get("parts", []):
            if isinstance(p, dict) and "text" in p:
                parts.append(types.Part(text=p["text"]))
            elif isinstance(p, str):
                parts.append(types.Part(text=p))
        formatted_history.append({"role": h["role"], "parts": parts})

    chat_session = client.chats.create(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            tools=[git_ops.list_files, git_ops.read_file],
            system_instruction=(
                """You are the Technical Lead and Prompt Architect. You have **READ-ONLY** access to the user's codebase.

**CRITICAL RULES:**
1. **Explore First:** When the user asks a question, you must **IMMEDIATELY** use `list_files` and `read_file` to investigate. **NEVER** ask the user for file paths or code snippets. Find them yourself.
2. **Read-Only:** You cannot edit, write, or delete files. If code changes are required, you must describe them or generate a 'Jules Prompt'.
3. **Jules Prompt:** When the user asks to "write a prompt", "deploy", or "create instructions", you must generate a structured block starting with `## Jules Prompt` containing the specific context and acceptance criteria."""
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
        history=formatted_history,
    )

    def generate():
        full_response_text = ""
        for chunk in generate_response(chat_session, user_msg):
            yield chunk
            # Accumulate text for saving history
            if chunk.startswith("event: message"):
                try:
                    # chunk is "event: message\ndata: "..."\n\n"
                    lines = chunk.strip().split("\n")
                    for line in lines:
                        if line.startswith("data: "):
                            text_part = json.loads(line[6:])
                            full_response_text += text_part
                except Exception:
                    pass

        # Save model response
        if full_response_text:
            chat_manager.save_message("model", full_response_text)

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
