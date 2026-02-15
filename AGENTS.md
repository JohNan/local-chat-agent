# Agent Instructions for Gemini Local Agent

## Project Overview
This is a lightweight, self-hosted web interface acting as a "Prompt Architect" for another AI agent.
It runs on **Python 3.11+** using **FastAPI** and **Google Gemini API**.

## Architecture
- **Backend:** `app/` package (FastAPI). Entry point is `app/main.py`.
  - Routes: Defined in `app/main.py`.
  - Services: Business logic in `app/services/`.
    - `chat_manager.py`: Handles chat history persistence and pagination.
    - `git_ops.py`: Git operations and file system tools.
    - `rag_manager.py`: Handles RAG system and codebase indexing (uses ChromaDB).
    - `jules_api.py`: Manages integration with Jules API.
    - `task_manager.py`: Handles task persistence (`tasks.json`).
- **Frontend:** React + Vite (TypeScript). Build artifacts are served by FastAPI at `app/static/dist`.
- **Container:** Dockerized via `Dockerfile`.

## Development Rules
1. **Model:** Always ensure `gemini-3-pro-preview` is used.
2. **Formatting & Testing:** Run `black .`, `pylint app/`, and `pytest` before committing.
3. **RAG & Persistence:** The system uses ChromaDB for the RAG system (persisted locally). Task state is saved in `tasks.json`. Ensure `rag_manager.index_codebase_task` is called on startup and after git pulls.
4. **Security:** Never hardcode API keys. Use `os.environ.get("GOOGLE_API_KEY")` or `os.environ.get("JULES_API_KEY")`.
5. **Frontend State:** Complex scroll logic (lazy loading) is handled in `ChatInterface.tsx` using `useLayoutEffect`. Maintain this pattern to prevent scroll jumping.

## Testing

### Backend Tests & Linting
Run these commands to verify the backend:
1. `pytest`
2. `black --check .`
3. `PYTHONPATH=. pylint app/`

### Frontend Checks
Run these commands inside the `frontend/` directory:
1. `npm run lint`
2. `npm run build`

### Running the Server
To run the server locally for manual testing:
1. `source venv/bin/activate` (if applicable)
2. `export GOOGLE_API_KEY="test_key"` (or use real key from env)
3. `uvicorn app.main:app --reload`
