# Agent Rules & Architecture

## Core Principles
1.  **Prompt Architect**: This system is primarily a "Prompt Architect." It analyzes context to generate instructions for a coding agent.
2.  **Jules Integration**: It can deploy prompts to "Jules" via an external API.
3.  **Active CLI Mode**: (New) If enabled, the local CLI Engine (Gemini) can act as an autonomous implementation agent, performing file edits and running tests directly.
4.  **Read-Only by Default**: The backend is read-only unless "Active CLI Mode" or specific Jules deployment flows are triggered.

## Jules Prompt Standards
All prompts generated for Jules must follow this structure:
1.  **Heading**: `## Jules Prompt`. This MUST be the last heading in the architect's response.
2.  **Summary**: A one-sentence summary of the task with no markdown.
3.  **Core Instructions**:
    - **Initial Step**: Explicitly instruct Jules to read `AGENTS.md` before starting.
    - **Documentation**: Reference relevant files in `docs/` if created for the task.
4.  **Architecture Context (MUST follow the heading)**:
    - **ADR**: Include a Markdown Architecture Decision Record (ADR) justifying the proposed changes.
    - **Diagram**: Include a Mermaid.js diagram visualizing the architecture or flow.
5.  **Task Details**: Clear, actionable requirements and acceptance criteria.
6.  **Constraint**:
    - **Parsing Rule**: The deployment system extracts content after the **LAST** `## Jules Prompt` heading. This ensures that if multiple prompts are generated in a single response, only the final, corrected version is sent to Jules.
    - **Reasoning Exclusion**: The "Reasoning Trace" (tools and reasoning) is usually wrapped in `<details>` blocks and will be stripped by the deployment system. Do NOT put the ADR inside `<details>` blocks if you want it to be sent to Jules.

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
