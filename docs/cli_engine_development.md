# ACP and CLI Engine Development Rules

When working with the `CLILLMService` or any ACP-based agent integration:

1.  **Parity with SDK**: Always aim for parity with the `SDKLLMService`. This includes streaming reasoning (thoughts), tool execution status, and final answers.
2.  **ACP Chunk Handling**:
    -   `AgentMessageChunk`: Primary text.
    -   `AgentThoughtChunk`: Reasoning/thoughts. Must be added to `reasoning_trace` and broadcast to the UI.
    -   `ToolCallStart` / `ToolCallProgress`: Tool status. Must be broadcast as `event: tool` to the UI.
    -   `UserMessageChunk`: Must be handled to detect `turn_marker` in re-emitted history.
3.  **History Filtering**:
    -   Gemini CLI re-emits session history when resuming.
    -   Use a unique `turn_marker` (UUID) appended to the prompt.
    -   Ignore all chunks until the current turn's `turn_marker` is found.
    -   The marker may appear in `UserMessageChunk` or `AgentMessageChunk` depending on how the CLI re-emits.
4.  **Robust Extraction**:
    -   Always handle both object-based and dictionary-based content blocks.
    -   Support `TextContentBlock`, `ResourceContentBlock`, and `EmbeddedResourceContentBlock`.
5.  **Session Management**:
    -   Reuse `session_id` across turns to maintain context in the CLI.
    -   Ensure the connection remains open until the turn is fully complete.
