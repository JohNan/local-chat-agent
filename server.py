import os
import flask
import google.generativeai as genai
from flask import request, jsonify, render_template_string
import threading
import functools

app = flask.Flask(__name__)

# --- Configuration ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    print("Warning: GOOGLE_API_KEY environment variable not set.")

genai.configure(api_key=GOOGLE_API_KEY)

# Default to /codebase inside Docker, but fallback to current directory for local testing
CODEBASE_ROOT = "/codebase" if os.path.exists("/codebase") else "."

# --- Thread Local for Logs ---
request_context = threading.local()

def log_tool_usage(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Construct a log message
        arg_str = ", ".join([repr(a) for a in args] + [f"{k}={v!r}" for k, v in kwargs.items()])
        log_msg = f"🛠 {func.__name__}({arg_str})"

        # Append to thread local logs if initialized
        if hasattr(request_context, 'tool_logs'):
            request_context.tool_logs.append(log_msg)

        return func(*args, **kwargs)
    return wrapper

# --- Tools ---

@log_tool_usage
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
        dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', 'venv', '.env'}]

        for file in files:
            full_path = os.path.join(root, file)
            # Get relative path from CODEBASE_ROOT
            rel_path = os.path.relpath(full_path, CODEBASE_ROOT)
            files_list.append(rel_path)

    return files_list

@log_tool_usage
def read_file(filepath: str) -> str:
    """
    Reads and returns the text content of a file.
    """
    # Sanitize filepath
    if filepath.startswith("/"):
        filepath = filepath.lstrip("/")

    full_path = os.path.abspath(os.path.join(CODEBASE_ROOT, filepath))

    # Security check: Ensure we are still inside CODEBASE_ROOT
    root_abs = os.path.abspath(CODEBASE_ROOT)
    if not full_path.startswith(root_abs):
        return "Error: Access denied. Cannot read outside of codebase."

    if not os.path.exists(full_path):
        return f"Error: File {filepath} not found."

    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

tools = [list_files, read_file]

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

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, history: chatHistory })
                });

                const data = await response.json();

                if (data.tool_logs && data.tool_logs.length > 0) {
                   data.tool_logs.forEach(log => {
                       appendToolLog(log);
                   });
                }

                if (!response.ok) {
                    throw new Error(data.response || response.statusText);
                }

                appendMessage('ai', data.response);

                chatHistory.push({role: 'user', parts: [text]});
                chatHistory.push({role: 'model', parts: [data.response]});

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

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/chat', methods=['POST'])
def chat():
    # Initialize tool logs for this request
    request_context.tool_logs = []

    data = request.json
    user_msg = data.get('message')
    history = data.get('history', [])

    formatted_history = []
    for h in history:
        formatted_history.append({
            "role": h['role'],
            "parts": h['parts']
        })

    model = genai.GenerativeModel(
        model_name='gemini-3-pro-preview',
        tools=tools,
        system_instruction="You are the Technical Lead and Prompt Architect for this project. Your purpose is to analyze the user's local codebase and construct precise, high-context prompts that the user will send to another AI agent named 'Jules'.\n\nWhen the user asks for a feature or bug fix:\n1. Use your tools (`list_files`, `read_file`) to thoroughly investigate the relevant code.\n2. Explain your findings briefly to the user.\n3. Generate a 'Jules Prompt' block. This block must contain a standalone, technically detailed instruction that includes file paths, existing code context, and strict acceptance criteria. The user should be able to copy-paste this prompt directly to Jules to get the job done."
    )

    chat_session = model.start_chat(
        history=formatted_history,
        enable_automatic_function_calling=True
    )

    try:
        response = chat_session.send_message(user_msg)
        return jsonify({
            "response": response.text,
            "tool_logs": request_context.tool_logs
        })
    except Exception as e:
        return jsonify({
            "response": f"Server Error: {str(e)}",
            "tool_logs": request_context.tool_logs
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
