# pylint: disable=too-many-lines
"""
Service for LLM interactions and helper functions.
"""

import base64
import asyncio
import json
import uuid
import logging
import traceback
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Any

from google.genai import types
from acp import spawn_agent_process, text_block
from acp.interfaces import Client
from acp.schema import (
    ClientCapabilities,
    FileSystemCapabilities,
    AgentMessageChunk,
    McpServerStdio,
    EnvVariable,
    AgentThoughtChunk,
    UserMessageChunk,
    ToolCallStart,
    ToolCallProgress,
    TextContentBlock,
    RequestPermissionResponse,
    AllowedOutcome,
    DeniedOutcome,
)

from app.services import chat_manager, code_executor, git_ops, rag_manager, web_ops
from app.config import LLM_ENGINE


# pylint: disable=too-few-public-methods
@dataclass(slots=True)
class TurnContext:
    """Context for a single LLM turn."""

    system_instruction: str = ""
    is_new_context: bool = False


# pylint: disable=too-few-public-methods
class BaseLLMService(Protocol):
    """Protocol defining the interface for an LLM Service."""

    # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments
    async def execute_turn(
        self,
        chat_session: Any,
        current_msg: str,
        task_state: Any,
        turn_context: TurnContext | None = None,
        mode: str = "chat",
    ) -> tuple[defaultdict, list[str], str]:
        """Executes a single turn of the agent loop."""


logger = logging.getLogger(__name__)

# Global cache state
CACHE_STATE = {}
ACP_CLI_SESSION_ID = None

# Global MCP State
MCP_SESSIONS = {}
MCP_TOOL_DEFINITIONS = []
MCP_TOOL_TO_SESSION_MAP = {}


def clear_cache():
    """Clears the global cache state."""
    global ACP_CLI_SESSION_ID  # pylint: disable=global-statement
    CACHE_STATE.clear()
    ACP_CLI_SESSION_ID = None


def get_tool_config(client, enable_search, enable_embeddings=True):
    """Configures tools for the agent."""
    function_declarations = [
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.list_files
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.read_file
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_file_history
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_recent_commits
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.grep_code
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_file_outline
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.read_android_manifest
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.get_definition
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=web_ops.fetch_url
        ),
        types.FunctionDeclaration.from_callable(
            client=client, callable=git_ops.write_to_docs
        ),
    ]

    if enable_embeddings:
        function_declarations.append(
            types.FunctionDeclaration.from_callable(
                client=client, callable=rag_manager.search_codebase_semantic
            )
        )

    # Append MCP tools
    function_declarations.extend(MCP_TOOL_DEFINITIONS)

    google_search_tool = types.GoogleSearch() if enable_search else None

    return types.Tool(
        function_declarations=function_declarations,
        google_search=google_search_tool,
        code_execution=types.ToolCodeExecution(),
    )


def prepare_messages(user_msg, media):
    """
    Prepares messages for storage and Gemini API.
    Splits media into inline data for JSON storage and Blob objects for the SDK.
    """
    storage_parts = []
    gemini_msg = []

    if user_msg:
        storage_parts.append({"text": user_msg})
        gemini_msg.append(types.Part(text=user_msg))

    if media:
        for item in media:
            # For JSON storage
            storage_parts.append(
                {"inline_data": {"mime_type": item["mime_type"], "data": item["data"]}}
            )
            # For Gemini API
            gemini_msg.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type=item["mime_type"],
                        data=base64.b64decode(item["data"]),
                    )
                )
            )
    return storage_parts, gemini_msg


def format_history(
    history, include_last: bool = False
):  # pylint: disable=too-many-branches
    """Formats chat history for Gemini API, ensuring valid roles."""
    # Find last system message index
    start_index = 0
    for i, msg in enumerate(history):
        if msg.get("role") == "system":
            start_index = i + 1

    # Slice effective history
    history_subset = history[start_index:]

    formatted_history = []
    # We need to exclude the very last message (current user msg)
    # when initializing history, because send_message(user_msg) will add it again.
    # If include_last is True, we keep it (useful for counting tokens of the entire history).
    if include_last:
        history_for_gemini = history_subset
    else:
        history_for_gemini = history_subset[:-1] if history_subset else []

    for h in history_for_gemini:
        role = h["role"]

        parts = []
        has_function_response = False
        for p in h.get("parts", []):
            if isinstance(p, dict):
                if "functionResponse" in p:
                    has_function_response = True
                    parts.append(
                        types.Part.from_function_response(
                            name=p["functionResponse"]["name"],
                            response=p["functionResponse"]["response"],
                        )
                    )
                elif "functionCall" in p:
                    parts.append(
                        types.Part.from_function_call(
                            name=p["functionCall"]["name"],
                            args=p["functionCall"]["args"],
                        )
                    )
                elif "text" in p:
                    parts.append(types.Part(text=p["text"]))
                elif "inline_data" in p:
                    parts.append(
                        types.Part(
                            inline_data=types.Blob(
                                mime_type=p["inline_data"]["mime_type"],
                                data=base64.b64decode(p["inline_data"]["data"]),
                            )
                        )
                    )
            elif isinstance(p, str):
                parts.append(types.Part(text=p))

        # Map 'function' role to 'user' ONLY for legacy text-based function messages
        if role == "function" and not has_function_response:
            role = "user"

        formatted_history.append({"role": role, "parts": parts})
    return formatted_history


def get_cached_content_config(  # pylint: disable=too-many-locals
    client, full_history, system_instruction, model, ttl_minutes=60
):
    """
    Gets or creates a cache for the chat history, enabling reuse.
    Context caching is only available for input token counts >= 32,768.
    Returns: (cache_name, history_delta)
    """
    global CACHE_STATE  # pylint: disable=global-statement

    # Load documentation
    docs_content = ""
    docs_dir = Path("docs")
    if docs_dir.exists() and docs_dir.is_dir():
        for doc_file in docs_dir.glob("*.md"):
            try:
                docs_content += f"\n\n--- {doc_file.name} ---\n"
                docs_content += doc_file.read_text(encoding="utf-8")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning("Failed to read %s: %s", doc_file, e)

    if docs_content:
        system_instruction += f"\n\n### Architectural Guides\n{docs_content}"

    sys_hash = str(hash(system_instruction))

    # 1. Attempt Reuse
    if CACHE_STATE:
        cached_count = CACHE_STATE.get("message_count", 0)
        cached_sys_hash = CACHE_STATE.get("system_instruction_hash")
        cached_content_hash = CACHE_STATE.get("content_hash")

        if cached_sys_hash == sys_hash and len(full_history) >= cached_count:
            prefix = full_history[:cached_count]
            # Verify prefix matches cached content
            if str(hash(str(prefix))) == cached_content_hash:
                delta_history = full_history[cached_count:]
                # Reuse if delta isn't too large (e.g. < 20 messages)
                if len(delta_history) <= 20:
                    return CACHE_STATE["name"], delta_history

    # 2. Check if eligible for new cache
    total_text = str(system_instruction) + str(full_history)
    # Threshold: ~100k chars (approx 25k tokens, safe buffer for 32k requirement)
    if len(total_text) < 100000:
        # Too small, verify if we should clear stale cache
        if CACHE_STATE and len(full_history) < CACHE_STATE.get("message_count", 0):
            CACHE_STATE.clear()
        return None, full_history

    # 3. Create New Cache
    try:
        cache = client.caches.create(
            model=model,
            config=types.CreateCachedContentConfig(
                contents=full_history,
                system_instruction=system_instruction,
                ttl=f"{ttl_minutes * 60}s",
            ),
        )

        CACHE_STATE = {
            "name": cache.name,
            "message_count": len(full_history),
            "content_hash": str(hash(str(full_history))),
            "system_instruction_hash": sys_hash,
        }

        return cache.name, []

    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning("Failed to create context cache: %s", e)
        # Clear state if creation failed to avoid stale state issues?
        # Maybe not necessary, but safer.
        return None, full_history


async def stream_generator(queue: asyncio.Queue):
    """
    Reads from the queue and yields to the client.
    Handles client disconnects gracefully.
    """
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
    except GeneratorExit:
        logger.warning(
            "Client disconnected from stream. Worker continues in background."
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Stream generator error: %s", e)


TOOL_MAP = {
    "list_files": git_ops.list_files,
    "read_file": git_ops.read_file,
    "get_file_history": git_ops.get_file_history,
    "get_recent_commits": git_ops.get_recent_commits,
    "grep_code": git_ops.grep_code,
    "get_file_outline": git_ops.get_file_outline,
    "read_android_manifest": git_ops.read_android_manifest,
    "get_definition": git_ops.get_definition,
    "search_codebase_semantic": rag_manager.search_codebase_semantic,
    "code_execution": code_executor.execute_code,
    "run_programming_task": code_executor.execute_code,
    "fetch_url": web_ops.fetch_url,
    "write_to_docs": git_ops.write_to_docs,
}


async def _execute_tool(fc):
    """
    Executes a single tool call safely.
    Returns the result.
    """
    logger.info("Executing tool: %s args=%s", fc.name, fc.args)
    tool_func = TOOL_MAP.get(fc.name)
    if tool_func:
        try:
            if asyncio.iscoroutinefunction(tool_func):
                return await tool_func(**fc.args)
            # Tools are synchronous and blocking (e.g. file I/O).
            # Run them in a thread.
            return await asyncio.to_thread(tool_func, **fc.args)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error executing {fc.name}: {e}"

    # Check MCP tools
    session = MCP_TOOL_TO_SESSION_MAP.get(fc.name)
    if session:
        try:
            result = await session.call_tool(fc.name, arguments=fc.args)
            # Extract content from MCP result
            output_text = []
            if hasattr(result, "content"):
                for content in result.content:
                    if content.type == "text":
                        output_text.append(content.text)
                    elif content.type == "image":
                        output_text.append(f"[Image: {content.mimeType}]")
                    else:
                        output_text.append(str(content))
            else:
                output_text.append(str(result))

            return "\n".join(output_text)

        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error executing MCP tool {fc.name}: {e}"

    logger.warning("Unknown tool call: %s", fc.name)
    return f"Error: Tool {fc.name} not found."


# pylint: disable=too-few-public-methods
class SDKLLMService(BaseLLMService):
    """Implementation of the LLM service using the Google GenAI SDK."""

    # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments
    async def execute_turn(
        self,
        chat_session: Any,
        current_msg: str,
        task_state: Any,
        turn_context: TurnContext | None = None,
        mode: str = "chat",
    ) -> tuple[defaultdict, list[str], str]:
        del turn_context
        del mode
        return await self._run_loop(chat_session, current_msg, task_state)

    async def _stream_with_retry(
        self, chat_session, current_msg, turn: int, task_state: Any
    ):
        """
        Attempts to establish a stream with retry logic for transient errors.
        """
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries + 1):
            try:
                return await chat_session.send_message_stream(current_msg)
            except Exception as e:  # pylint: disable=broad-exception-caught
                error_str = str(e)
                is_retryable = (
                    "503" in error_str
                    or "Service Unavailable" in error_str
                    or "high demand" in error_str
                )

                if is_retryable and attempt < max_retries:
                    logger.warning(
                        "[TURN %d] Gemini 503/Busy. Retrying in %ds (Attempt %d/%d)...",
                        turn,
                        retry_delay,
                        attempt + 1,
                        max_retries,
                    )
                    # Notify frontend via tool status
                    msg = (
                        f"Gemini API is busy. Retrying in {retry_delay} seconds... "
                        f"(Attempt {attempt + 1}/{max_retries})"
                    )
                    await task_state.broadcast(
                        f"event: tool\ndata: {json.dumps(msg)}\n\n"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    raise e

        raise RuntimeError("Failed to establish stream after retries.")

    async def _process_turn_stream(
        self, chat_session, current_msg, turn: int, task_state: Any
    ) -> tuple[str, list]:
        """
        Handles the streaming interaction with the LLM for a single turn, including retries.
        Returns the full text of the turn and any tool calls found.
        """
        turn_text_parts = []
        tool_calls = []

        stream = await self._stream_with_retry(
            chat_session, current_msg, turn, task_state
        )

        async for chunk in stream:
            # Text processing
            try:
                chunk_text = ""
                # Safely extract text from parts if available
                if hasattr(chunk, "parts"):
                    for part in chunk.parts:
                        if part.text:
                            chunk_text += part.text
                # Fallback for simple text responses (if parts is missing/empty)
                elif hasattr(chunk, "text"):
                    try:
                        chunk_text = chunk.text
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass

                if chunk_text:
                    turn_text_parts.append(chunk_text)
                    await task_state.broadcast(
                        f"event: message\ndata: {json.dumps(chunk_text)}\n\n"
                    )
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("[TURN %d] Error processing chunk text: %s", turn, e)

            # Tool call processing
            try:
                # 1. Primary check: chunk.function_calls (Gemini SDK v0.3+)
                if hasattr(chunk, "function_calls") and chunk.function_calls:
                    tool_calls.extend(chunk.function_calls)
                # 2. Fallback check: chunk.parts (Legacy)
                elif hasattr(chunk, "parts"):
                    for part in chunk.parts:
                        if part.function_call:
                            tool_calls.append(part.function_call)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("[TURN %d] Error processing chunk tool calls: %s", turn, e)

        full_turn_text = "".join(turn_text_parts)
        return full_turn_text, tool_calls

    async def _execute_turn_tools(
        self,
        tool_calls: list,
        turn: int,
        task_state: Any,
        tool_usage_counts: defaultdict,
    ) -> list[types.Part]:
        """
        Executes the tools for a single turn and returns the response parts.
        """
        logger.debug("[TURN %d] Executing tools...", turn)
        tool_descriptions = []
        for fc in tool_calls:
            tool_usage_counts[fc.name] += 1
            if fc.name == "read_file":
                tool_descriptions.append(f"Reading file '{fc.args.get('filepath')}'")
            elif fc.name == "list_files":
                tool_descriptions.append(
                    f"Listing directory '{fc.args.get('directory')}'"
                )
            elif fc.name == "get_file_history":
                tool_descriptions.append(
                    f"Getting history for '{fc.args.get('filepath')}'"
                )
            elif fc.name == "get_recent_commits":
                tool_descriptions.append("Getting recent commits")
            elif fc.name == "get_file_outline":
                tool_descriptions.append(f"Outlining '{fc.args.get('filepath')}'")
            elif fc.name == "read_android_manifest":
                tool_descriptions.append("Reading Android Manifest")
            elif fc.name == "search_codebase_semantic":
                tool_descriptions.append(
                    f"Searching codebase for '{fc.args.get('query')}'"
                )
            elif fc.name in ("code_execution", "run_programming_task"):
                tool_descriptions.append("Running python code")
            else:
                tool_descriptions.append(f"Running {fc.name}")

        joined_descriptions = ", ".join(tool_descriptions)
        # STRICT JSON ENCODING prevents newlines from breaking SSE
        tool_status_msg = f"{joined_descriptions}..."
        await task_state.broadcast(
            f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n"
        )

        # Parallel Execution
        tool_results = await asyncio.gather(*[_execute_tool(fc) for fc in tool_calls])

        response_parts = []
        for fc, result in zip(tool_calls, tool_results):
            response_parts.append(
                types.Part.from_function_response(
                    name=fc.name, response={"result": result}
                )
            )
        return response_parts

    async def _run_loop(
        self, chat_session, current_msg, task_state: Any
    ) -> tuple[defaultdict, list[str], str]:
        """
        Runs the main agent loop.
        Returns collected tool usage, reasoning trace, and final answer.
        """
        turn = 0
        tool_usage_counts = defaultdict(int)
        reasoning_trace = []
        final_answer = ""

        while turn < 50:
            turn += 1
            logger.debug("[TURN %d] Sending message to SDK", turn)

            # self._process_turn_stream raises exception on failure, which will be caught by caller
            try:
                full_turn_text, tool_calls = await self._process_turn_stream(
                    chat_session, current_msg, turn, task_state
                )
            except Exception:  # pylint: disable=broad-exception-caught
                # Log the error with turn context before propagating
                logger.error("Turn %d Error: %s", turn, traceback.format_exc())
                raise

            if full_turn_text:
                reasoning_trace.append(full_turn_text)

            if not tool_calls:
                if reasoning_trace:
                    final_answer = reasoning_trace.pop()
                break

            current_msg = await self._execute_turn_tools(
                tool_calls, turn, task_state, tool_usage_counts
            )

            if turn == 50:
                # pylint: disable=line-too-long
                final_answer = (
                    "I've reached the maximum number of steps (50) for this turn. "
                    "I've performed several actions, which you can see in the reasoning trace below. "
                    "Would you like me to continue where I left off?"
                )
                # pylint: enable=line-too-long
                await task_state.broadcast(
                    f"event: message\ndata: {json.dumps(final_answer)}\n\n"
                )

        return tool_usage_counts, reasoning_trace, final_answer


# pylint: disable=too-many-instance-attributes
class ACPClientHandler(Client):
    """ACP Client to handle streaming updates from Gemini CLI."""

    def __init__(self, task_state, turn_marker: str):
        super().__init__()
        self.task_state = task_state
        self.turn_marker = turn_marker
        logger.info(
            "[ACP] ACPClientHandler started. Waiting for turn_marker: %s", turn_marker
        )
        self.final_answer = ""
        self.raw_final_answer = ""
        self.marker_found = False
        self.tool_usage_counts = defaultdict(int)
        self.reasoning_trace = []
        self.current_text_segment = ""
        self.user_msg_seen = False
        self.last_agent_text = ""
        self.last_thought_text = ""
        self.last_user_text = ""

    # pylint: disable=arguments-differ,arguments-renamed,unused-argument
    async def read_text_file(
        self, session_id: str, path: str, **kwargs: Any
    ) -> str:
        """Reads a text file from the codebase."""
        return git_ops.read_file(path)

    async def write_text_file(
        self, session_id: str, path: str, content: str, **kwargs: Any
    ) -> None:
        """Writes a text file to the codebase."""
        git_ops.write_file_safe(path, content)

    async def delete_file(self, session_id: str, filepath: str, **kwargs: Any) -> None:
        """Deletes a file from the codebase."""
        # pylint: disable=import-outside-toplevel
        import os

        git_ops._validate_path(filepath)  # pylint: disable=protected-access
        os.remove(filepath)

    async def list_directory(
        self, session_id: str, directory: str, **kwargs: Any
    ) -> list:
        """Lists files in a directory."""
        return git_ops.list_files(directory)

    async def run_terminal_command(
        self, session_id: str, command: str, **kwargs: Any
    ) -> str:
        """Runs a terminal command robustly."""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=git_ops.CODEBASE_ROOT,
            )
            stdout, stderr = await proc.communicate()

            output = []
            if stdout:
                output.append(stdout.decode().strip())
            if stderr:
                output.append(f"STDERR:\n{stderr.decode().strip()}")

            return "\n".join(output) if output else "Command executed with no output"
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error executing terminal command: %s", e)
            return f"Error executing command: {e}"

    # pylint: enable=arguments-differ,arguments-renamed,unused-argument

    # pylint: disable=too-many-return-statements
    def _extract_text(self, content: Any) -> str:
        """Robustly extracts text from dictionaries, lists, or Pydantic models."""
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(self._extract_text(item) for item in content)
        if isinstance(content, dict):
            return content.get("text", content.get("thought", ""))

        if isinstance(content, TextContentBlock):
            return str(content.text)

        # Fallback for dynamic/duck-typed Pydantic objects if isinstance fails
        if hasattr(content, "text") and getattr(content, "text", None) is not None:
            return str(getattr(content, "text"))
        if (
            hasattr(content, "thought")
            and getattr(content, "thought", None) is not None
        ):
            return str(getattr(content, "thought"))

        return ""

    # pylint: disable=too-many-branches,too-many-statements,too-many-return-statements
    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        update_type = type(update).__name__
        logger.debug("[ACP] session_update: %s - %s", update_type, str(update)[:100])

        if isinstance(update, (ToolCallStart, ToolCallProgress)):
            if not self.marker_found:
                logger.warning("[ACP] Fallback triggered by ToolCallStart")
                self.marker_found = True
                # Flush existing buffer
                combined = self.last_agent_text + self.last_thought_text
                if combined:
                    await self._process_new_text(combined)

            title = "Tool operation"
            if hasattr(update, "title") and update.title:
                title = update.title
            elif hasattr(update, "status") and update.status:
                title = update.status

            if (
                isinstance(update, ToolCallStart)
                and hasattr(update, "title")
                and update.title
            ):
                self.tool_usage_counts[update.title] += 1
                if self.current_text_segment:
                    self.reasoning_trace.append(self.current_text_segment)
                    self.current_text_segment = ""
            # STRICT JSON ENCODING prevents newlines from breaking SSE
            tool_status_msg = f"{title}..."
            await self.task_state.broadcast(
                f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n"
            )
            await self.task_state.broadcast(
                f"event: log\ndata: {json.dumps(tool_status_msg)}\n\n"
            )
            return

        chunk = ""
        is_user_msg = False
        is_thought = False
        is_agent = False

        if isinstance(update, AgentMessageChunk):
            chunk = self._extract_text(update.content)
            is_agent = True
        elif isinstance(update, AgentThoughtChunk):
            chunk = self._extract_text(update.content)
            is_thought = True
        elif isinstance(update, UserMessageChunk):
            chunk = self._extract_text(update.content)
            is_user_msg = True

        if not chunk:
            return

        if is_user_msg:
            self.user_msg_seen = True

        new_raw_text = ""
        if is_agent:
            if chunk.startswith(self.last_agent_text):
                new_raw_text = chunk[len(self.last_agent_text) :]
            else:
                new_raw_text = chunk
            self.last_agent_text = chunk
        elif is_thought:
            if chunk.startswith(self.last_thought_text):
                new_raw_text = chunk[len(self.last_thought_text) :]
            else:
                new_raw_text = chunk
            self.last_thought_text = chunk
        elif is_user_msg:
            # We don't broadcast user messages, but we add them to
            # raw_final_answer to find the marker
            if chunk.startswith(self.last_user_text):
                new_raw_text = chunk[len(self.last_user_text) :]
            else:
                new_raw_text = chunk
            self.last_user_text = chunk

        self.raw_final_answer += new_raw_text

        # Always check for the marker in raw_final_answer if we haven't found it yet
        if not self.marker_found:
            idx = self.raw_final_answer.find(self.turn_marker)
            if idx != -1:
                logger.info("[ACP] Turn marker found at index %d", idx)
                self.marker_found = True

                # We found the marker. Extract text *after* the marker
                new_text_after_marker = self.raw_final_answer[
                    idx + len(self.turn_marker) :
                ].lstrip("\n")
                if new_text_after_marker and not is_user_msg:
                    await self._process_new_text(new_text_after_marker)
            elif is_agent or is_thought:
                # Fallbacks if marker isn't found yet but we are receiving agent
                # content
                if not self.user_msg_seen:
                    # pylint: disable=line-too-long
                    logger.warning(
                        "[ACP] Agent message received before user message. Assuming history echo is disabled."
                    )
                    # pylint: enable=line-too-long
                    self.marker_found = True
                    if new_raw_text and not is_user_msg:
                        await self._process_new_text(new_raw_text)
                elif len(self.last_agent_text) + len(self.last_thought_text) > 50:
                    logger.warning(
                        "[ACP] Fallback triggered by significant agent content without marker"
                    )
                    self.marker_found = True
                    # If we fallback due to significant content, it's safer to broadcast the
                    # accumulated text (this might be slightly duplicated with what was already
                    # buffered in current_text_segment, but we didn't broadcast it yet)
                    await self._process_new_text(
                        self.last_thought_text + self.last_agent_text
                    )
        else:
            if new_raw_text and not is_user_msg:
                await self._process_new_text(new_raw_text)

    async def _process_new_text(self, text: str):
        self.current_text_segment += text
        await self.task_state.broadcast(f"event: message\ndata: {json.dumps(text)}\n\n")
        await self.task_state.broadcast(f"event: log\ndata: {json.dumps(text)}\n\n")

    # pylint: disable=too-many-locals
    async def request_permission(
        self, options: Any, session_id: str, tool_call: Any, **kwargs: Any
    ) -> Any:
        try:
            # pylint: disable=import-outside-toplevel
            from app.config import CLI_REQUIRE_APPROVAL

            selected_option = "approve"
            if options and len(options) > 0:
                selected_option = options[0].option_id

            if CLI_REQUIRE_APPROVAL:
                tool_name = getattr(tool_call, "name", "unknown_tool")
                tool_args = getattr(tool_call, "arguments", {})

                payload = {"name": tool_name, "arguments": tool_args}
                action_id, future = self.task_state.action_registry.register(payload)

                event_data = {
                    "action_id": action_id,
                    "type": "tool_call",
                    "data": payload,
                }
                event_str = json.dumps(event_data)

                await self.task_state.broadcast(
                    f"event: action_required\ndata: {event_str}\n\n"
                )

                result = await future
                decision = result.decision

                if decision in ("approve", "edit"):
                    return RequestPermissionResponse(
                        outcome=AllowedOutcome(
                            option_id=selected_option, outcome="selected"
                        )
                    )

                return RequestPermissionResponse(
                    outcome=DeniedOutcome(outcome="rejected")
                )

            return RequestPermissionResponse(
                outcome=AllowedOutcome(option_id=selected_option, outcome="selected")
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error in request_permission: %s", e)
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="rejected"))


# pylint: disable=too-few-public-methods
class CLILLMService(BaseLLMService):
    """Implementation of the LLM service using the Gemini CLI via ACP."""

    # pylint: disable=too-many-locals, too-many-arguments, too-many-positional-arguments, too-many-branches, too-many-statements
    async def execute_turn(
        self,
        chat_session: Any,
        current_msg: str,
        task_state: Any,
        turn_context: TurnContext | None = None,
        mode: str = "chat",
    ) -> tuple[defaultdict, list[str], str]:
        turn_context = turn_context or TurnContext()
        turn_marker = f"==JULES_TURN_{uuid.uuid4().hex[:8]}=="
        client = ACPClientHandler(task_state, turn_marker)

        try:
            model = await asyncio.to_thread(chat_manager.get_setting, "default_model")
            if not model:
                model = "gemini-2.5-flash"

            async with spawn_agent_process(
                client,
                "gemini",
                "--acp",
                "--output-format",
                "stream-json",
                "--model",
                model,
                cwd=git_ops.CODEBASE_ROOT,
            ) as (conn, _proc):
                await conn.initialize(
                    protocol_version=1,
                    client_capabilities=ClientCapabilities(
                        fs=FileSystemCapabilities(
                            read_text_file=True, write_text_file=True
                        ),
                        terminal=True,
                    ),
                )

                prompt_msg = current_msg
                if mode == "implementation":
                    impl_instruction = (
                        "You are an autonomous coding agent. "
                        "Implement the given instructions, modify files using the provided tools, "
                        "and execute tests to verify your changes. If tests fail, "
                        "diagnose and fix the errors. Ensure to use tools autonomously. "
                        "You must use replace_in_file_safe and write_file_safe "
                        "for all file modifications to avoid platform bugs. "
                        "If the built-in shell tool fails for complex redirections, "
                        "use the MCP-provided run_shell_command tool."
                    )
                    prompt_msg = f"{impl_instruction}\n\n{current_msg}"
                elif turn_context.is_new_context and turn_context.system_instruction:
                    prompt_msg = f"{turn_context.system_instruction}\n\n{current_msg}"

                # Append the unique marker to identify where the new response begins
                prompt_msg = f"{prompt_msg}\n\n{turn_marker}\n\n"

                global ACP_CLI_SESSION_ID  # pylint: disable=global-statement
                current_session_id = None

                # pylint: disable=import-outside-toplevel
                import os
                import sys

                app_root = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", "..")
                )
                mcp_server_script = os.path.join(app_root, "mcp_server.py")

                env_vars = [
                    EnvVariable(name="PYTHONPATH", value=app_root),
                    EnvVariable(name="CODEBASE_ROOT", value=git_ops.CODEBASE_ROOT),
                ]
                if "GOOGLE_API_KEY" in os.environ:
                    env_vars.append(
                        EnvVariable(
                            name="GOOGLE_API_KEY", value=os.environ["GOOGLE_API_KEY"]
                        )
                    )

                mcp_server_config = McpServerStdio(
                    name="JulesAppServer",
                    command=sys.executable,
                    args=[mcp_server_script],
                    env=env_vars,
                )

                if ACP_CLI_SESSION_ID:
                    try:
                        await conn.load_session(
                            cwd=git_ops.CODEBASE_ROOT,
                            session_id=ACP_CLI_SESSION_ID,
                            mcp_servers=[mcp_server_config],
                        )
                        current_session_id = ACP_CLI_SESSION_ID
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        logger.warning(
                            "Failed to load session %s: %s", ACP_CLI_SESSION_ID, e
                        )
                        current_session_id = None

                if not current_session_id:
                    session = await conn.new_session(
                        cwd=git_ops.CODEBASE_ROOT, mcp_servers=[mcp_server_config]
                    )
                    current_session_id = session.session_id
                    ACP_CLI_SESSION_ID = current_session_id

                await conn.prompt(
                    session_id=current_session_id,
                    prompt=[text_block(prompt_msg)],
                )

        except Exception as e:  # pylint: disable=broad-exception-caught
            error_str = str(e).lower()
            if (
                "missing or not configured" in error_str
                or "authentication" in error_str
                or "credentials" in error_str
            ):
                # pylint: disable=line-too-long
                err_msg = "Authentication failed for Gemini CLI. If you are running in Docker, please run `gemini auth` on your host machine and mount your ~/.config/gemini and ~/.config/gcloud directories into the container as shown in docker-compose.example.yml."
                # pylint: enable=line-too-long
                await task_state.broadcast(f'event: error\ndata: "{err_msg}"\n\n')
                return client.tool_usage_counts, client.reasoning_trace, err_msg
            raise e

        if not client.marker_found:
            fallback_text = (
                client.last_agent_text
                or client.last_thought_text
                or client.raw_final_answer[-500:]
            )
            if fallback_text and fallback_text not in client.current_text_segment:
                client.current_text_segment += fallback_text

        if client.current_text_segment:
            client.reasoning_trace.append(client.current_text_segment)

        if client.reasoning_trace:
            client.final_answer = client.reasoning_trace[-1]

        return client.tool_usage_counts, client.reasoning_trace, client.final_answer


def get_llm_service() -> BaseLLMService:
    """Returns the configured LLM service instance."""

    if LLM_ENGINE == "cli":
        return CLILLMService()
    return SDKLLMService()
