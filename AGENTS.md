# Agent Rules & Architecture

## Core Principles
1.  **Prompt Architect**: This system is primarily a "Prompt Architect." It analyzes context to generate instructions for a coding agent.
2.  **Jules Integration**: It can deploy prompts to "Jules" via an external API.
3.  **Active CLI Mode**: (New) If enabled, the local CLI Engine (Gemini) can act as an autonomous implementation agent, performing file edits and running tests directly.
4.  **Read-Only by Default**: The backend is read-only unless "Active CLI Mode" or specific Jules deployment flows are triggered.

## Directory Structure
- `app/`: Python backend (FastAPI).
- `frontend/`: React frontend (Vite + TypeScript).
- `docs/`: Architecture Decision Records (ADRs) and documentation.
- `app/services/`: Core logic (LSP, Git, LLM, RAG).
- `app/routers/`: API endpoints.

## Coding Standards
- Use `asyncio` for I/O bound tasks.
- Keep the `CLILLMService` modular to support different modes (Chat, Edit, Implementation).
- Frontend components should be functional and use Hooks.

## Active CLI Mode Rules
- Must use a specialized system prompt for implementation tasks.
- Must provide clear feedback to the user via SSE or status endpoints.
- Should ideally work on a temporary git branch for safety.
