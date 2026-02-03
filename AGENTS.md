# Agent Instructions for Gemini Local Agent

## Project Overview
This is a lightweight, self-hosted web interface acting as a "Prompt Architect" for another AI agent.
It runs on **Python 3.11+** using **FastAPI** and **Google Gemini API**.

## Architecture
- **Backend:** `app/` package (FastAPI). Entry point is `app/main.py`.
  - Routes: Defined in `app/main.py`.
  - Services: Business logic in `app/services/`.
- **Frontend:** `app/static/dist/index.html`. Served by FastAPI.
- **Container:** Dockerized via `Dockerfile`.

## Development Rules
1. **Model:** Always ensure `gemini-3-pro-preview` is used.
2. **Formatting:** Run `black app/` before submitting any code changes.
3. **No Database:** Do NOT add SQL/Vector databases. We use "Function Calling" to read files directly.
4. **Security:** Never hardcode API keys. Use `os.environ.get("GOOGLE_API_KEY")`.

## Testing
To test the server locally inside this environment:
1. `source venv/bin/activate` (if applicable)
2. `export GOOGLE_API_KEY="test_key"` (or use real key from env)
3. `uvicorn app.main:app --reload`
