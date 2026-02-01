import os
import re
import json
import flask
import subprocess
import functools
import traceback
import requests
from google import genai
from google.genai import types
from flask import request, jsonify, render_template_string, stream_with_context, Response

app = flask.Flask(__name__)

# --- Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
JULES_API_KEY = os.environ.get("JULES_API_KEY")

# Default to /codebase inside Docker, but fallback to current directory for local testing
CODEBASE_ROOT = "/codebase" if os.path.exists("/codebase") else "."

@functools.lru_cache(maxsize=1)
def get_jules_source():
    # 1. Environment Variable
    env_source = os.environ.get("JULES_SOURCE")
    if env_source:
        return env_source

    # 2. Git Config Parsing
    try:
        git_config_path = os.path.join(CODEBASE_ROOT, ".git", "config")
        if os.path.exists(git_config_path):
            with open(git_config_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Simple regex to find the url in [remote "origin"] block
            remote_block_match = re.search(r'\[remote "origin"\](.*?)(?=\[|$)', content, re.DOTALL)
            if remote_block_match:
                block_content = remote_block_match.group(1)
                url_match = re.search(r'url\s*=\s*(\S+)', block_content)
                if url_match:
                    url = url_match.group(1)

                    if url.endswith(".git"):
                        url = url[:-4]

                    # Parse user/repo from github url
                    github_match = re.search(r'github\.com[:/]([\w.-]+)/([\w.-]+)', url)
                    if github_match:
                        return f"sources/github/{github_match.group(1)}/{github_match.group(2)}"
    except Exception as e:
        print(f"Warning: Failed to parse git config: {e}")

    return None

def get_git_info():
    try:
        # Get remote URL
        remote_url_bytes = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=CODEBASE_ROOT, stderr=subprocess.DEVNULL
        )
        remote_url = remote_url_bytes.decode("utf-8").strip()

        # Parse user/repo
        project = "Unknown"
        if "github.com" in remote_url:
            match = re.search(r'github\.com[:/]([\w.-]+)/([\w.-]+)', remote_url)
            if match:
                project = f"{match.group(1)}/{match.group(2)}"
                if project.endswith(".git"):
                    project = project[:-4]
        else:
            project = remote_url.split("/")[-1] # Fallback
            if project.endswith(".git"):
                project = project[:-4]

        # Get current branch
        branch_bytes = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=CODEBASE_ROOT, stderr=subprocess.DEVNULL
        )
        branch = branch_bytes.decode("utf-8").strip()

        return {"project": project, "branch": branch}
    except Exception:
        return {"project": "No Git Repo", "branch": "-"}

@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify(get_git_info())

@app.route("/api/git_pull", methods=["POST"])
def api_git_pull():
    try:
        output = subprocess.check_output(
            ["git", "pull"],
            cwd=CODEBASE_ROOT,
            stderr=subprocess.STDOUT
        )
        return jsonify({"success": True, "output": output.decode("utf-8")})
    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "output": e.output.decode("utf-8")})
    except Exception as e:
        return jsonify({"success": False, "output": str(e)})

print(f"DEBUG: API Key present: {bool(GOOGLE_API_KEY)}")
print(f"DEBUG: Active Jules Source: {get_jules_source()}")

if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY environment variable not set.")

client = genai.Client(api_key=GOOGLE_API_KEY)

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
    <div id="header" style="padding: 10px 20px; background-color: var(--chat-bg); border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: bold;">Gemini Agent</span>
        <div>
            <span style="margin-right: 15px;">📂 <span id="repo-status">Loading...</span></span>
            <button onclick="gitPull()" style="padding: 5px 10px; font-size: 0.9em;">⬇️ Git Pull</button>
        </div>
    </div>

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

                // Check for Jules Prompt marker
                if (currentAiText.includes("## Jules Prompt")) {
                    const deployBtn = document.createElement('button');
                    deployBtn.innerHTML = "🚀 Start Jules Task";
                    deployBtn.style.marginTop = "10px";
                    deployBtn.onclick = function() { deploy(this); };

                    if (aiMessageDiv) {
                        aiMessageDiv.appendChild(deployBtn);
                        chatContainer.scrollTop = chatContainer.scrollHeight;
                    }
                }

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

        async function deploy(btn) {
            // Find the prompt text. It should be in the message div containing this button.
            // We assume the prompt is inside a code block or the whole message.
            // Let's grab the text content of the parent message div.
            const messageDiv = btn.parentElement;
            let promptText = messageDiv.innerText;

            // Clean up the text: remove the button text itself and maybe the "## Jules Prompt" header if needed.
            // But sending the whole thing is probably fine, Jules is smart.
            // However, cleaning it a bit is better.
            promptText = promptText.replace(btn.innerText, '').trim();

            btn.innerText = "⏳ Sending...";
            btn.disabled = true;

            try {
                const response = await fetch('/api/deploy_to_jules', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: promptText })
                });

                const data = await response.json();

                if (data.success) {
                    const sessionName = data.result.name || "Unknown Session";
                    btn.innerText = `✅ Started! (${sessionName})`;
                    btn.onclick = null; // Disable further clicks
                } else {
                    btn.innerText = "❌ Error";
                    alert("Error deploying: " + data.error);
                    btn.disabled = false;
                }
            } catch (e) {
                console.error(e);
                btn.innerText = "❌ Error";
                alert("Error deploying: " + e.message);
                btn.disabled = false;
            }
        }

        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                document.getElementById('repo-status').innerText = `${data.project} (${data.branch})`;
            } catch(e) {
                console.error(e);
                document.getElementById('repo-status').innerText = "Error";
            }
        }

        async function gitPull() {
             const btn = document.querySelector('button[onclick="gitPull()"]');
             const originalText = btn.innerText;
             btn.innerText = "⏳ Pulling...";
             btn.disabled = true;

             try {
                const res = await fetch('/api/git_pull', {method: 'POST'});
                const data = await res.json();
                alert(data.output);
             } catch(e) {
                alert("Error: " + e.message);
             } finally {
                btn.innerText = originalText;
                btn.disabled = false;
                updateStatus(); // Refresh status just in case
             }
        }

        // Call on load
        updateStatus();
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
        yield from generate_response(chat_session, user_msg)

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


def send_task_to_jules(prompt_text):
    api_key = JULES_API_KEY or GOOGLE_API_KEY
    if not api_key:
        raise ValueError("JULES_API_KEY or GOOGLE_API_KEY not set")

    source_id = get_jules_source()
    if not source_id:
        raise ValueError("Could not detect Git repository. Please set JULES_SOURCE in .env")

    url = "https://jules.googleapis.com/v1alpha/sessions"
    headers = {
        "X-Goog-Api-Key": api_key,
        "Content-Type": "application/json"
    }

    data = {
        "prompt": prompt_text,
        "sourceContext": {
            "source": source_id
        }
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code != 200:
        raise Exception(f"Jules API Error: {response.status_code} - {response.text}")

    return response.json()


@app.route("/api/deploy_to_jules", methods=["POST"])
def deploy_to_jules():
    try:
        data = request.json
        prompt_text = data.get("prompt")

        if not prompt_text:
            return jsonify({"success": False, "error": "No prompt provided"}), 400

        result = send_task_to_jules(prompt_text)

        return jsonify({
            "success": True,
            "result": result
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
