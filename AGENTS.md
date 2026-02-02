# Agent Instructions for Gemini Local Agent

## Project Overview
This is a lightweight, self-hosted web interface acting as a "Prompt Architect" for another AI agent.
It runs on **Python 3.9+** using **Flask** and **Google Gemini API**.

## Architecture
- **Backend:** `app/` package (Flask Blueprint structure). Entry point is `app/main.py`.
  - Routes: Defined in `app/routes.py`.
  - Services: Business logic in `app/services/`.
- **Frontend:** `app/templates/index.html`. Renders Markdown chat bubbles.
- **Container:** Dockerized via `Dockerfile` and `docker-compose.yml`.

## Development Rules
1. **Model:** Always ensure `gemini-3-pro-preview` is used in `app/routes.py`.
2. **Formatting:** Run `black app/` before submitting any code changes.
3. **No Database:** Do NOT add SQL/Vector databases. We use "Function Calling" to read files directly.
4. **Security:** Never hardcode API keys. Use `os.environ.get("GOOGLE_API_KEY")`.

## Testing
To test the server locally inside this environment:
1. `source venv/bin/activate`
2. `export GOOGLE_API_KEY="test_key"` (or use real key from env)
3. `python -m app.main`
