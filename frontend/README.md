# Gemini Code Agent - Frontend

This directory contains the React + TypeScript frontend for the Gemini Code Agent. It provides a chat interface to interact with the backend agent, featuring markdown rendering, code highlighting, and tool execution status.

## Architecture

The frontend is built using **React**, **Vite**, and **TypeScript**.

### Key Components

-   **`App.tsx`**: The main application component. It manages the global state, including:
    -   `messages`: The array of chat messages.
    -   `model`: The currently selected Gemini model.
    -   `webSearchEnabled`: State for the web search toggle.
    -   `loadHistory`: Function to fetch paginated history from the backend.
    -   `sendMessage`: Handles sending user input and processing the streaming response.

-   **`ChatInterface.tsx`**: The main chat view area.
    -   **Lazy Loading**: Implements efficient scrolling by loading older messages as the user scrolls to the top.
    -   **Scroll Management**: Uses `useLayoutEffect` to maintain scroll position when history is prepended, preventing "scroll jumping".

-   **`MessageBubble.tsx`**: Renders individual chat messages.
    -   Supports Markdown rendering.
    -   Displays syntax-highlighted code blocks.
    -   Shows tool execution status (e.g., "Reading file...").

-   **`InputArea.tsx`**: The user input component.
    -   Handles text input.
    -   Provides the model selection dropdown.
    -   Includes the "Deploy to Jules" button.

-   **`Header.tsx`**: The application header.
    -   Contains the "Settings" modal for configuration (Git Pull, Repo Status).

## State Management

State is primarily managed in `App.tsx` using standard React hooks (`useState`, `useEffect`, `useCallback`).
-   **Chat History**: Loaded via the `/api/history` endpoint.
-   **Streaming**: Chat responses are streamed using Server-Sent Events (SSE), with the `sendMessage` function parsing the stream to update message content and tool status in real-time.

## Development

### Prerequisites

-   Node.js (v18+)
-   npm

### Commands

-   **Install Dependencies**:
    ```bash
    npm install
    ```

-   **Run Development Server**:
    ```bash
    npm run dev
    ```
    This will start the Vite dev server at `http://localhost:5173`. Note that you need the backend running on port 5000 for API calls to work (proxied via `vite.config.ts`).

-   **Linting**:
    ```bash
    npm run lint
    ```

-   **Build**:
    ```bash
    npm run build
    ```
    The build artifacts are output to `../app/static/dist` (as configured in `vite.config.ts`) to be served by the FastAPI backend.
