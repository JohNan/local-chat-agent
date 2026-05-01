# CLI Engine Development Rules

When developing or modifying the `CLILLMService` or `ACPClientHandler`, follow these rules to ensure stability and parity with the SDK engine.

## 1. Streaming and Events
- **Parity**: Every piece of text (message or thought) MUST be broadcast as `event: message`.
- **Tool Status**: Tool calls and progress MUST be broadcast as `event: tool`.
- **Reasoning**: `AgentThoughtChunk` should be treated as part of the reasoning trace.
- **Delta Handling**: The handler must correctly handle both full-text re-emission and delta-only chunks.

## 2. Synchronization
- **Turn Marker**: Use a unique `turn_marker` (e.g., UUID-based) for every turn to identify the start of the new response in re-emitted history.
- **Marker Detection**: Logging MUST be present to verify when the marker is found.
- **History Filtering**: Chunks received before the marker is found (or `UserMessageChunk` containing the marker) MUST NOT be broadcast to the UI.

## 3. Data Extraction
- **Robustness**: `_extract_text` must handle:
    - Pydantic models with `text` attribute.
    - Dictionaries with `text` key.
    - Lists of content blocks.
    - `AgentThoughtChunk` specific fields (like `thought` or `content.text`).

## 4. Return Values
- **Execute Turn**: Must return `(tool_usage_counts, reasoning_trace, final_answer)`.
- **Reasoning Trace**: Should contain all text segments (thoughts and messages) produced during the turn.
- **Final Answer**: Should be the final message produced after all tool calls are finished.

## 5. Logging
- **Debug Level**: Use `logger.debug` for every `session_update` to capture the chunk type and a snippet of its content.
- **State Changes**: Log when the marker is found and when segments are finalized.

## 6. Process Management
- **Wait for Completion**: `CLILLMService.execute_turn` must wait for the agent's turn to be fully completed before returning and closing the connection.
- **Session Persistence**: Maintain `ACP_CLI_SESSION_ID` across turns to allow the CLI to maintain context.
