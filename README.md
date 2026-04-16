# Gemini Code Agent: Prompt Architect

> **⚠️ Security Warning**: This tool provides read/write access to your filesystem. Run LOCALLY only. DO NOT expose port 5000.

A lightweight, self-hosted web interface that acts as a "Prompt Architect" for another AI agent named "Jules". This tool analyzes your local codebase using Google's Gemini API and Automatic Function Calling to generate precise, high-context prompts.

## Architecture
- **[AGENTS.md](AGENTS.md)**: Architecture and rules for the **Coding Agent (Jules)**.

## Features

-   **Prompt Architect**: Generates structured "Jules Prompt" blocks with file paths and acceptance criteria.
-   **Multi-language LSP**: Integrated Language Server Protocol support (Python, TypeScript, Kotlin) for precise "Go to Definition" and code intelligence.
-   **Semantic Code Search (RAG)**: Uses ChromaDB and Gemini Embeddings for context-aware code retrieval and semantic search.
-   **MCP Support**: Extensible tool usage via Model Context Protocol (MCP), allowing dynamic integration of external tools.
-   **Sticky Personas**: Intelligent intent classification (UI, Mobile, Architect, CI/CD) that adapts the agent's behavior and persists across sessions.
-   **SQLite Persistence**: Robust data storage for chat history, tasks, and settings (`app.db`), replacing legacy JSON files.
-   **Git Integration**: Perform `git pull` operations directly from the UI to keep your local codebase up-to-date.
-   **Direct Jules Deployment**: Deploy prompts directly to Jules (creating sessions/PRs) from the UI.
-   **Task Management**: View and track Jules tasks via the UI.
-   **Lightweight**: Runs on older hardware (no AVX required).

## Available Tools

The agent is equipped with the following tools to explore and understand your codebase:

-   `list_files`: Lists files in a directory (respects `.gitignore`).
-   `read_file`: Reads the content of a specific file.
-   `grep_code`: Searches for code patterns using regex.
-   `get_file_history`: Retrieves the git history of a file.
-   `get_recent_commits`: Shows the most recent commits in the repository.
-   `get_file_outline`: Extracts the structure (classes, functions) of a file.
-   `read_android_manifest`: Parses `AndroidManifest.xml` for package and activity details.

## API Endpoints

The backend exposes several key endpoints:

-   `GET /api/history`: Retrieves paginated chat history.
-   `GET /api/models`: Lists available Gemini models.
-   `GET /api/tasks`: Retrieves list of Jules tasks.
-   `GET /api/status`: Retrieves repository status and active persona.
-   `POST /api/context_reset`: Inserts a context reset marker into the history.
-   `POST /api/git_pull`: Executes a `git pull` command.
-   `POST /api/deploy_to_jules`: Deploys current prompt to Jules.
-   `POST /api/stop`: Stops the current generation.
