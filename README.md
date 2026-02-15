# Gemini Code Agent: Prompt Architect

> **⚠️ Security Warning**: This tool provides read/write access to your filesystem. Run LOCALLY only. DO NOT expose port 5000.

A lightweight, self-hosted web interface that acts as a "Prompt Architect" for another AI agent named "Jules". This tool analyzes your local codebase using Google's Gemini API and Automatic Function Calling to generate precise, high-context prompts.

## Features

-   **Prompt Architect**: Generates structured "Jules Prompt" blocks with file paths and acceptance criteria.
-   **Chat History Persistence**: Chat history is automatically saved to a flat JSON file (`chat_history.json`), allowing you to resume sessions across restarts.
-   **Lazy Loading**: The frontend efficiently handles large chat histories by lazy loading messages as you scroll up, ensuring high performance.
-   **Context Reset**: Insert a "Context Reset" marker to start a fresh logical session without deleting your entire history.
-   **Git Integration**: Perform `git pull` operations directly from the UI to keep your local codebase up-to-date.
-   **RAG System**: Uses ChromaDB and Gemini Embeddings for semantic search and code retrieval.
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

## Prerequisites

- Docker and Docker Compose
- Google Gemini API Key (requires `gemini-3-pro-preview` access)
- Jules API Key (optional, for deployment features)

## Setup

1.  **Get your Google API Key** from [Google AI Studio](https://makersuite.google.com/app/apikey).
2.  **Configure Environment**:
    Copy the example environment file and set your key:
    ```bash
    cp .env.example .env
    # Edit .env and paste your GOOGLE_API_KEY
    ```
3.  **Local Setup (Optional)**:
    For local development, use the setup script which uses `uv` for faster installation:
    ```bash
    ./setup_env.sh
    ```
4.  **Configure Docker Compose**:
    Copy the example compose file:
    ```bash
    cp docker-compose.example.yml docker-compose.yml
    ```

## Running the Agent

Run the application using Docker Compose:

```bash
docker-compose up --build
```

The current directory is mounted to `/codebase` in the container.

## Usage

1.  Open `http://localhost:5000`.
2.  **Select Model**: You can dynamically switch between available Gemini models using the dropdown in the header.
3.  Ask for help with your code.
    -   Example: "Analyze `server.py` and tell me how to add a new route."
4.  The agent will investigate and produce a **Jules Prompt**.
5.  Copy this prompt and send it to your Jules agent.

## Development / Contributing

To develop locally, you can verify your changes using the following commands:

### Backend Verification

-   **Linting**:
    ```bash
    black .
    PYTHONPATH=. pylint app/
    ```
-   **Testing**:
    ```bash
    pytest
    ```

### Frontend Verification

-   **Linting**:
    ```bash
    cd frontend && npm run lint
    ```
-   **Building**:
    ```bash
    cd frontend && npm run build
    ```

### Docker Verification

To match the CI environment exactly:

1.  **Build the Image**:
    ```bash
    docker build -t gemini-agent .
    ```
2.  **Run Checks**:
    ```bash
    # Run Tests
    docker run --rm -v $(pwd):/codebase -w /codebase gemini-agent pytest

    # Run Black
    docker run --rm -v $(pwd):/codebase -w /codebase gemini-agent black --check .

    # Run Pylint
    docker run --rm -v $(pwd):/codebase -w /codebase -e PYTHONPATH=. gemini-agent pylint app/
    ```

## Architecture

-   **Backend**: FastAPI (Python)
-   **AI**: Google Gemini 3 Pro Preview
-   **Frontend**: React + Vite (TypeScript)
-   **Deployment**: Docker
