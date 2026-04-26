# Prompt for Implementing Gemini CLI Migration

Based on the architectural analysis in `docs/gemini_cli_migration.md`, please implement the abstraction layer to support switching between the `google-genai` SDK and the Gemini CLI.

**Goal:**
Refactor the LLM execution logic to allow seamlessly switching between the existing SDK approach and a new CLI-based approach, ensuring the existing SDK implementation remains fully functional.

**Specific Tasks:**

1.  **Configuration Flag:**
    *   In `app/config.py`, introduce a new environment variable/setting: `LLM_ENGINE` (default to `"sdk"`).
    *   Possible values should be `"sdk"` and `"cli"`.

2.  **LLM Service Abstraction (`app/services/llm_service.py`):**
    *   Extract the current SDK-based LLM execution logic into a class named `SDKLLMService`.
    *   Create a common interface (e.g., a base class or structural protocol `BaseLLMService`) that requires an `execute_turn` method (or similar) to handle the agent loop.
    *   Create a skeleton class `CLILLMService` that implements this interface.
    *   Implement a factory function `get_llm_service()` that reads `config.LLM_ENGINE` and returns the appropriate service instance.

3.  **CLI Subprocess Implementation (`CLILLMService`):**
    *   In `CLILLMService`, use `asyncio.create_subprocess_exec` to invoke the `gemini` command: `gemini -p "<user_prompt>" --output-format stream-json --acp`.
    *   Read the stdout stream asynchronously line-by-line.
    *   Parse the JSON output from the CLI and yield SSE-compatible events back to the `TaskState` (mirroring how `_process_turn_stream` currently yields chunks).

4.  **Agent Engine Refactoring (`app/agent_engine.py`):**
    *   Update `run_agent_task` to use the `BaseLLMService` abstraction instead of hardcoding the SDK `_run_loop`.
    *   Ensure that when `LLM_ENGINE == "sdk"`, the exact existing behavior is preserved without regressions.

5.  **Tool/MCP Preparation (Skeleton):**
    *   Create a placeholder script `mcp_server.py` in the root directory that will eventually host the Python tools (like `list_files`, `rag_manager.search_codebase_semantic`) as an MCP server for the CLI to connect to. You do not need to implement the full MCP server logic yet, just the scaffolding.

**Verification:**
*   Ensure that running `pytest` with `LLM_ENGINE="sdk"` passes all existing tests.
*   Ensure that the application starts up correctly when `LLM_ENGINE="cli"` is set, even if the MCP tool integration is not yet fully functional.

Please proceed with implementing this abstraction layer.
