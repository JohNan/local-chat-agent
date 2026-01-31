# Gemini Code Agent

A lightweight, self-hosted web interface to chat with your local codebase using Google's Gemini API. This agent uses Automatic Function Calling to explore and read your files on demand, without the need for local vector databases or embeddings.

## Prerequisites

- Docker and Docker Compose
- Google Gemini API Key

## Setup

1.  **Get your Google API Key** from [Google AI Studio](https://makersuite.google.com/app/apikey).
2.  **Set the environment variable** (or pass it directly in the docker-compose command).

    ```bash
    export GOOGLE_API_KEY="your_api_key_here"
    ```

## Running the Agent

Run the application using Docker Compose:

```bash
docker-compose up --build
```

This will build the image and start the server. The current directory (where `docker-compose.yml` resides) is mounted into the container at `/codebase`, allowing the agent to read the files in this repository.

## Usage

1.  Open your browser and navigate to `http://localhost:5000`.
2.  Start chatting with the agent!
    -   Example: "What files are in the root directory?"
    -   Example: "Explain the logic in `server.py`."
    -   Example: "How does the Dockerfile set up the environment?"

The interface will show a "🛠" indicator whenever the agent uses a tool to list or read files.

## Architecture

-   **Backend**: Flask (Python)
-   **AI**: Google Gemini 1.5 Flash (via `google-generativeai` SDK)
-   **Frontend**: Embedded HTML/JS with Markdown support
-   **Deployment**: Docker

## Notes

-   The agent operates in read-only mode on the mounted codebase.
-   No data is indexed or stored locally.
-   Designed for older hardware (no AVX requirement).
