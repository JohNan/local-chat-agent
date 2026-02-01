import os
import json
import flask
import traceback
from google import genai
from google.genai import types
from flask import request, jsonify, render_template_string, stream_with_context, Response

app = flask.Flask(__name__)

# --- Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
print(f"DEBUG: API Key present: {bool(GOOGLE_API_KEY)}")

if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY environment variable not set.")

client = genai.Client(api_key=GOOGLE_API_KEY)

# Default to /codebase inside Docker, but fallback to current directory for local testing
CODEBASE_ROOT = "/codebase" if os.path.exists("/codebase") else "."

# --- Tools ---

def list_files(directory: str = ".") -> list[str]:
    """
    Lists all files in the given directory (recursive), ignoring specific directories.
    Returns a list of relative file paths.
    """
    files_list = []

    # Sanitize directory input to be relative to root
    if directory.startswith("/"):
        directory = directory.lstrip("/")

    base_path = os.path.join(CODEBASE_ROOT, directory)

    if not os.path.exists(base_path):
        return [f"Error: Directory {directory} does not exist."]

    for root, dirs, files in os.walk(base_path):
        # Ignore directories
        dirs[:] = [
            d
            for d in dirs
            if d not in {".git", "__pycache__", "node_modules", "venv", ".env"}
        ]

        for file in files:
            full_path = os.path.join(root, file)
            # Get relative path from CODEBASE_ROOT
            rel_path = os.path.relpath(full_path, CODEBASE_ROOT)
            files_list.append(rel_path)

    return files_list

def read_file(filepath: str) -> str:
    """
    Reads and returns the text content of a file.
    """
    # Sanitize filepath
    if filepath.startswith("/"):
        filepath = filepath.lstrip("/")

    full_path = os.path.abspath(os.path.join(CODEBASE_ROOT, filepath))
    root_abs = os.path.abspath(CODEBASE_ROOT)

    # Security check: Ensure we are still inside CODEBASE_ROOT using commonpath
    try:
        if os.path.commonpath([full_path, root_abs]) != root_abs:
            return "Error: Access denied. Cannot read outside of codebase."
    except ValueError:
        # Can happen on different drives on Windows, essentially outside
        return "Error: Access denied. Cannot read outside of codebase."

    if not os.path.exists(full_path):
        return f"Error: File {filepath} not found."

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

TOOL_MAP = {
    'list_files': list_files,
    'read_file': read_file
}

# --- Chat Interface ---

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gemini Code Agent</title>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        :root {
            --bg-color: #1e1e1e;
            --chat-bg: #252526;
            --user-msg-bg: #0e639c;
            --ai-msg-bg: #3c3c3c;
            --text-color: #d4d4d4;
            --input-bg: #3c3c3c;
            --border-color: #454545;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        #chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .message {
            max-width: 80%;
            padding: 10px 15px;
            border-radius: 8px;
            line-height: 1.5;
        }
        .user-message {
            align-self: flex-end;
            background-color: var(--user-msg-bg);
        }
        .ai-message {
            align-self: flex-start;
            background-color: var(--ai-msg-bg);
        }
        .error-message {
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
        }
        .tool-usage {
            font-size: 0.85em;
            color: #aaa;
            font-style: italic;
            margin-bottom: 5px;
            border-left: 2px solid #007acc;
            padding-left: 8px;
            align-self: flex-start;
        }
        #input-area {
            padding: 20px;
            background-color: var(--chat-bg);
            border-top: 1px solid var(--border-color);
            display: flex;
            gap: 10px;
        }
        input[type="text"] {
            flex: 1;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid var(--border-color);
            background-color: var(--input-bg);
            color: var(--text-color);
            outline: none;
        }
        button {
            padding: 10px 20px;
            background-color: var(--user-msg-bg);
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            opacity: 0.9;
        }
        pre {
            background-color: #1e1e1e;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
        code {
            font-family: 'Consolas', 'Monaco', monospace;
        }
    </style>
</head>
<body>
    <div id="chat-container"></div>
    <div id="input-area">
        <input type="text" id="user-input" placeholder="Ask about your code..." onkeypress="if(event.key==='Enter') sendMessage()">
        <button onclick="sendMessage()">Send</button>
    </div>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const userInput = document.getElementById('user-input');

        let chatHistory = [];

        async function sendMessage() {
            const text = userInput.value.trim();
            if (!text) return;

            appendMessage('user', text);
            userInput.value = '';

            // Add to history
            chatHistory.push({role: 'user', parts: [{text: text}]});

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, history: chatHistory })
                });

                if (!response.ok) {
                    throw new Error(response.statusText);
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                let aiMessageDiv = null;
                let currentAiText = "";
                let buffer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const parts = buffer.split('\\n\\n');
                    buffer = parts.pop(); // Keep incomplete part

                    for (const part of parts) {
                        const lines = part.split('\\n');
                        let event = null;
                        let data = '';

                        for (const line of lines) {
                            if (line.startsWith('event: ')) {
                                event = line.substring(7).trim();
                            } else if (line.startsWith('data: ')) {
                                data = line.substring(6);
                            }
                        }

                        if (event === 'message') {
                            if (!aiMessageDiv) {
                                aiMessageDiv = appendMessage('ai', '');
                            }
                            try {
                                const textChunk = JSON.parse(data);
                                currentAiText += textChunk;
                                aiMessageDiv.innerHTML = marked.parse(currentAiText);
                            } catch (e) {
                                console.error('Error parsing JSON:', e);
                            }
                        } else if (event === 'tool') {
                            appendToolLog(data);
                        } else if (event === 'error') {
                            appendMessage('ai error-message', data);
                        }
                    }
                    chatContainer.scrollTop = chatContainer.scrollHeight;
                }

                chatHistory.push({role: 'model', parts: [{text: currentAiText}]});

            } catch (error) {
                console.error('Error:', error);
                appendMessage('ai error-message', `Error: ${error.message}`);
            }
        }

        function appendMessage(sender, text) {
            const div = document.createElement('div');
            // If sender has multiple classes (e.g. 'ai error-message'), split and add
            div.className = `message ${sender.replace(' ', ' ')}`;
            if (sender.includes('error-message')) {
                div.classList.add('error-message');
                div.classList.add('ai-message');
            } else {
                div.className = `message ${sender}-message`;
            }

            div.innerHTML = marked.parse(text);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
            return div;
        }

        function appendToolLog(text) {
             const div = document.createElement('div');
            div.className = `tool-usage`;
            div.innerText = text;
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)

def generate_response(session, message):
    try:
        response_stream = session.send_message_stream(message)

        for chunk in response_stream:
            if not chunk.candidates:
                continue

            part = chunk.candidates[0].content.parts[0]

            if part.function_call:
                fc = part.function_call
                args_repr = ", ".join(f"{k}={v!r}" for k,v in fc.args.items()) if fc.args else ""

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
                        name=fc.name,
                        response={"result": result}
                    )
                )

                yield from generate_response(session, fn_response_part)
                return

            elif part.text:
                yield f"event: message\ndata: {json.dumps(part.text)}\n\n"

    except Exception as e:
        traceback.print_exc()
        yield f"event: error\ndata: {json.dumps(str(e))}\n\n"


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    user_msg = data.get("message")
    history = data.get("history", [])

    formatted_history = []
    # Basic history reconstruction.
    # Note: Complex history with previous function calls is not fully handled here
    # as we rely on the client sending simplified text history or the server being stateless.
    # For a robust production app, we'd need to reconstruct types.Part properly including FunctionCall/Response.
    for h in history:
        parts = []
        for p in h["parts"]:
            if isinstance(p, dict) and 'text' in p:
                parts.append(types.Part(text=p['text']))
            elif isinstance(p, str):
                parts.append(types.Part(text=p))
            # Ignore others for now as we don't send them back yet
        formatted_history.append({"role": h["role"], "parts": parts})

    chat_session = client.chats.create(
        model="gemini-2.0-flash",
        config=types.GenerateContentConfig(
            tools=[list_files, read_file],
            system_instruction=(
                "You are a Technical Lead. "
                "1. **Default Mode (Consultant):** When the user asks questions, use your tools to read code, explain logic, and discuss architectural changes conversationally. Do NOT output a formal prompt in this mode. Just help the user understand and plan. "
                "2. **Action Mode (Architect):** ONLY when the user explicitly says a trigger phrase like 'Create a prompt for Jules', 'Write instructions', or 'Ready to code', then you must summarize the previous discussion and generate the structured '## Jules Prompt' block with strict acceptance criteria and file contexts."
            ),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        ),
        history=formatted_history,
    )

    def generate():
        yield from generate_response(chat_session, user_msg)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
