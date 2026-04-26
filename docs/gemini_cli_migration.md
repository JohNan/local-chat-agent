# Gemini CLI Migration Analysis

This document outlines the architectural feasibility and design for replacing the `google-genai` SDK with the Gemini CLI as the backend execution engine for the Gemini Code Agent, while preserving the ability to switch between them seamlessly.

## Motivation
The primary motivation is to utilize the Gemini CLI, which may be included in specific subscription models, as an alternative to the pay-as-you-go API keys required by the GenAI SDK.

## Analysis of Gemini CLI Capabilities
Based on the `gemini --help` output and available CLI packages:
1. **Execution Mode**: The CLI supports headless/non-interactive mode via `-p` (prompt) which can be leveraged programmatically.
2. **Output**: It supports `--output-format json` and `--output-format stream-json`, which makes parsing structured responses and simulating streaming easier.
3. **Tool Calling (Automatic Function Calling)**:
   - The current SDK architecture heavily relies on Gemini's native Automatic Function Calling (defining tools via schemas and handling execution callbacks).
   - The CLI uses MCP (Model Context Protocol) and extensions to handle tools internally within its own agentic loop.
   - We would need to register our existing Python functions (like `list_files`, `search_codebase_semantic`) as MCP servers or use a bridging mechanism, rather than passing JSON schemas directly in the request payload.
4. **Context & Caching**: The current system uses the SDK's `caches.create` for context caching. The CLI handles session history internally (via `--resume`), but explicit low-level context caching control is obfuscated.
5. **Embeddings**: The CLI is primarily a chat/agent tool. It likely does not expose a direct command for generating raw embeddings (e.g., `gemini-embedding-001` or `text-embedding-004`), which is currently required by `rag_manager.py` for codebase search. We would either need to retain the SDK specifically for embeddings or find an alternative embedding CLI command.

## Proposed Architecture

To support switching between the GenAI SDK and the Gemini CLI without breaking existing functionality, we should introduce an abstraction layer.

### 1. Abstracting the LLM Service
Create an interface (e.g., `BaseLLMService`) with two implementations:
- `SDKLLMService`: Uses the existing `google-genai` SDK logic.
- `CLILLMService`: Uses `asyncio.create_subprocess_exec` to spawn the `gemini` command.

### 2. Configuration Switch
Add a configuration flag in `app/config.py` (e.g., `LLM_ENGINE="sdk" | "cli"`) to determine which service to instantiate in `app/agent_engine.py` and `app/services/llm_service.py`.

### 3. CLI Subprocess Wrapper
The `CLILLMService` will execute the CLI command:
```bash
gemini -p "<user_prompt>" --output-format stream-json --acp
```
We would use `asyncio.create_subprocess_exec` to read stdout asynchronously. The output stream must be parsed line-by-line to extract the generated text and emit SSE events to the frontend, mirroring the `_process_turn_stream` logic.

### 4. Tool Integration (The Challenge)
Since the CLI relies on MCP for tool integration, we must run an MCP server alongside the CLI that exposes our Python tools.
1. `gemini mcp add my-python-tools "python mcp_server.py"`
2. The CLI will handle the tool execution loop internally.
3. This means our existing `_execute_turn_tools` loop in `app/agent_engine.py` might become redundant when using the CLI, as the CLI will print the final result. However, we would lose the granular SSE tracking of tool executions unless the `--output-format stream-json` provides detailed tool invocation logs.

### 5. Managing History
Instead of maintaining a massive array of message dictionaries (`types.Part`) and context caches, the `CLILLMService` will rely on the CLI's internal session management. We can use `--resume <session_id>` to continue conversations.

### 6. Embeddings
We will likely need to keep the SDK enabled (even if heavily rate-limited or using a free tier) *strictly* for the `rag_manager.py` to generate vector embeddings, unless the CLI exposes a hidden embedding command.

## Conclusion
Yes, it is possible to use the Gemini CLI in the backend. However, it represents a paradigm shift from **"Backend orchestrates the tool loop"** to **"CLI orchestrates the tool loop"**.

**Implementation Steps:**
1. Implement `BaseLLMService`.
2. Convert `llm_service.py` to `SDKLLMService`.
3. Create `CLILLMService` wrapping `asyncio.create_subprocess_exec`.
4. Create an MCP Server wrapper for existing `git_ops` and `rag_manager` functions to serve the CLI.
5. Update `agent_engine.py` to route based on `config.LLM_ENGINE`.
