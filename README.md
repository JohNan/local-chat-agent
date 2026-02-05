# Gemini Code Agent: Prompt Architect

A lightweight, self-hosted web interface that acts as a "Prompt Architect" for another AI agent named "Jules". This tool analyzes your local codebase using Google's Gemini API and Automatic Function Calling to generate precise, high-context prompts.

## Features

-   **Prompt Architect**: Generates structured "Jules Prompt" blocks with file paths and acceptance criteria.
-   **No Vector DB**: Uses real-time file exploration (`list_files`, `read_file`) instead of stale embeddings.
-   **Lightweight**: Runs on older hardware (no AVX required).

## Prerequisites

- Docker and Docker Compose
- Google Gemini API Key (requires `gemini-3-pro-preview` access)

## Setup

1.  **Get your Google API Key** from [Google AI Studio](https://makersuite.google.com/app/apikey).
2.  **Configure Environment**:
    Copy the example environment file and set your key:
    ```bash
    cp .env.example .env
    # Edit .env and paste your GOOGLE_API_KEY
    ```
3.  **Configure Docker Compose**:
    Copy the example compose file:
    ```bash
    cp docker-compose.example.yml docker-compose.yml
    ```

## Running the Agent

Run the application using Docker Compose:

```bash
docker-compose up --build
```

The current directory is mounted to `/codebase` in the container (read-only).

## Usage

1.  Open `http://localhost:5000`.
2.  Ask for help with your code.
    -   Example: "Analyze `server.py` and tell me how to add a new route."
3.  The agent will investigate and produce a **Jules Prompt**.
4.  Copy this prompt and send it to your Jules agent.

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
