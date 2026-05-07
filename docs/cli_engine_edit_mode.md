# Edit Mode for CLI Engine

## Overview
Edit Mode (Human-in-the-Loop) allows users to intercept, inspect, and modify tool calls proposed by the agent before they are executed. This is particularly important for the CLI Engine where the agent might otherwise execute destructive commands or use incorrect parameters.

## Architectural Components

### 1. Action Registry
A central registry in `app/services/task_manager.py` (or `app/agent_engine.py`) that manages pending user interventions.
- **PendingAction**: A dataclass containing the Action ID, the payload (tool call), and an `asyncio.Future`.

### 2. ACP Interception
The `ACPClientHandler` (in `app/services/llm_service.py`) is the gateway for tool calls from the Gemini CLI.
- `request_permission(tool_call)`: Instead of returning `{"outcome": "approved"}`, it will now:
    1. Generate a unique `action_id`.
    2. Register the action and get a `Future`.
    3. Broadcast `event: action_required` via the SSE stream.
    4. `await` the `Future`.
    5. Return the result based on the user's decision.

### 3. SSE Protocol
New event: `action_required`
```json
{
  "action_id": "uuid-v4",
  "type": "tool_call",
  "data": {
    "name": "read_file",
    "arguments": { "filepath": "app/main.py" }
  }
}
```

### 4. Resolution API
New endpoint: `POST /api/chat/action/resolve`
**Body:**
```json
{
  "action_id": "uuid-v4",
  "decision": "approve" | "reject" | "edit",
  "edited_arguments": { ... } (optional)
}
```

## Implementation Plan

1. **Backend Infrastructure**:
   - Implement `ActionRegistry` in `app/agent_engine.py`.
   - Update `TaskState` to hold an instance of `ActionRegistry`.
2. **CLI Engine Hook**:
   - Modify `ACPClientHandler.request_permission` to use the registry.
3. **API Endpoint**:
   - Add the resolution endpoint in `app/routers/chat.py`.
4. **UI Updates (Separate Task)**:
   - UI must handle the `action_required` event and show a blocking dialog.
