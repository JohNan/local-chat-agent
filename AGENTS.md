# Agent Instructions for Gemini Local Agent

## Project Overview
This is a lightweight, self-hosted web interface acting as a "Prompt Architect" for another AI agent.
It runs on **Python 3.9+** using **Flask** and **Google Gemini API**.

## Architecture
- **Backend:** `server.py` (Single-file Flask app). Handles API calls and file reading tools.
- **Frontend:** Embedded HTML/JS inside `server.py`. Renders Markdown chat bubbles.
- **Container:** Dockerized via `Dockerfile` and `docker-compose.yml`.

## Development Rules
1. **Model:** Always ensure `gemini-3-pro-preview` is used in `server.py`.
2. **Formatting:** Run `black server.py` before submitting any code changes.
3. **No Database:** Do NOT add SQL/Vector databases. We use "Function Calling" to read files directly.
4. **Security:** Never hardcode API keys. Use `os.environ.get("GOOGLE_API_KEY")`.

## Testing
To test the server locally inside this environment:
1. `source venv/bin/activate`
2. `export GOOGLE_API_KEY="test_key"` (or use real key from env)
3. `python server.py`
