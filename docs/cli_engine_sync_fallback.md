# ADR: CLI Engine Synchronization Fallback (Updated)

## Status
Accepted

## Context
The `CLILLMService` uses a unique `turn_marker` appended to the user prompt to identify where the new agent response begins in the ACP stream.

In multi-turn conversations, calling `load_session` often causes the CLI to echo previous turn history. If the current prompt echo is missing or arrives late, the agent may start responding while the handler is still waiting for the marker. If history was echoed, the `user_msg_seen` flag is set, blocking the fallback and causing the new response to be ignored.

Additionally, streaming updates from different CLI versions may be cumulative or incremental. The handler must correctly extract deltas without being confused by the prompt prefix in the buffer.

## Decision
We will implement "Smart Synchronization" in `ACPClientHandler`:
1. **Marker-First**: Search `raw_final_answer` for `turn_marker`.
2. **Signal-Based Fallback**: Trigger fallback if `marker_found` is False and we see:
   - Agent content with no previous user message.
   - OR a `ToolCallStart` (strong turn indicator).
   - OR significant agent content after a user message that lacked the marker.
3. **Robust Delta Extraction**: Track `last_text_by_type` to handle cumulative vs incremental chunks independently of the prompt buffer.
4. **Safe Return**: `execute_turn` will ensure a final answer is returned even if the marker was never found.

## Consequences
- **High Compatibility**: Works with all Gemini CLI versions regardless of echo settings.
- **Clean UI**: Prevents "A AB ABC" cumulative text jumps.
- **Reliable History**: Multi-turn conversations will correctly show reasoning and final messages.
