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
    AgentThoughtChunk,
    UserMessageChunk,
    ToolCallStart,
    ToolCallProgress,
    TextContentBlock,
)

from app.services import chat_manager, code_executor, git_ops, rag_manager, web_ops
from app.config import LLM_ENGINE

logger = logging.getLogger(__name__)

# pylint: disable=too-few-public-methods
@dataclass(slots=True)
class TurnContext:
    """Context for a single LLM turn."""

    system_instruction: str = ""
    is_new_context: bool = False


# pylint: disable=too-few-public-methods
class BaseLLMService(Protocol):
    """Protocol defining the interface for an LLM Service."""

    # pylint: disable=too-many-locals
    async def execute_turn(
        self,
        chat_session: Any,
        current_msg: str,
        task_state: Any,
        turn_context: TurnContext | None = None,
    ) -> tuple[defaultdict, list[str], str]:
        ...


CACHE_STATE = {}
ACP_CLI_SESSION_ID = None


def get_cached_content(
    client, model, full_history, system_instruction, ttl_minutes=60
):
    """
    Manages context caching to reduce tokens/cost.
    Returns (cache_name, delta_history).
    """
    global CACHE_STATE  # pylint: disable=global-statement

    # Simplified hash of system instructions
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
            return await asyncio.to_thread(tool_func, **fc.args)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error executing {fc.name}: {e}"

    # Check MCP tools
    session = MCP_TOOL_TO_SESSION_MAP.get(fc.name)
    if session:
        try:
            result = await session.call_tool(fc.name, arguments=fc.args)
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

    async def execute_turn(
        self,
        chat_session: Any,
        current_msg: str,
        task_state: Any,
        turn_context: TurnContext | None = None,
    ) -> tuple[defaultdict, list[str], str]:
        del turn_context
        return await self._run_loop(chat_session, current_msg, task_state)

    async def _stream_with_retry(
        self, chat_session, current_msg, turn: int, task_state: Any
    ):
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
                        turn, retry_delay, attempt + 1, max_retries
                    )
                    msg = f"Gemini API is busy. Retrying in {retry_delay} seconds..."
                    await task_state.broadcast(f"event: tool\ndata: {json.dumps(msg)}\n\n")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise e
        raise RuntimeError("Failed to establish stream after retries.")

    async def _process_turn_stream(
        self, chat_session, current_msg, turn: int, task_state: Any
    ) -> tuple[str, list]:
        turn_text_parts = []
        tool_calls = []
        stream = await self._stream_with_retry(chat_session, current_msg, turn, task_state)
        async for chunk in stream:
            try:
                chunk_text = ""
                if hasattr(chunk, "parts"):
                    for part in chunk.parts:
                        if part.text:
                            chunk_text += part.text
                elif hasattr(chunk, "text"):
                    try:
                        chunk_text = chunk.text
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
                if chunk_text:
                    turn_text_parts.append(chunk_text)
                    await task_state.broadcast(f"event: message\ndata: {json.dumps(chunk_text)}\n\n")
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("[TURN %d] Error processing chunk text: %s", turn, e)
            try:
                if hasattr(chunk, "function_calls") and chunk.function_calls:
                    tool_calls.extend(chunk.function_calls)
                elif hasattr(chunk, "parts"):
                    for part in chunk.parts:
                        if part.function_call:
                            tool_calls.append(part.function_call)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("[TURN %d] Error processing chunk tool calls: %s", turn, e)
        full_turn_text = "".join(turn_text_parts)
        return full_turn_text, tool_calls

    async def _execute_turn_tools(
        self, tool_calls: list, turn: int, task_state: Any, tool_usage_counts: defaultdict
    ) -> list[types.Part]:
        tool_descriptions = []
        for fc in tool_calls:
            tool_usage_counts[fc.name] += 1
            if fc.name == "read_file":
                tool_descriptions.append(f"Reading file '{fc.args.get('filepath')}'")
            elif fc.name == "list_files":
                tool_descriptions.append(f"Listing directory '{fc.args.get('directory')}'")
            elif fc.name == "get_file_history":
                tool_descriptions.append(f"Getting history for '{fc.args.get('filepath')}'")
            elif fc.name == "get_recent_commits":
                tool_descriptions.append("Getting recent commits")
            elif fc.name == "get_file_outline":
                tool_descriptions.append(f"Outlining '{fc.args.get('filepath')}'")
            elif fc.name == "read_android_manifest":
                tool_descriptions.append("Reading Android Manifest")
            elif fc.name == "search_codebase_semantic":
                tool_descriptions.append(f"Searching codebase for '{fc.args.get('query')}'")
            elif fc.name in ("code_execution", "run_programming_task"):
                tool_descriptions.append("Running python code")
            else:
                tool_descriptions.append(f"Running {fc.name}")

        joined_descriptions = ", ".join(tool_descriptions)
        tool_status_msg = f"{joined_descriptions}..."
        await task_state.broadcast(f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n")

        tool_results = await asyncio.gather(*[_execute_tool(fc) for fc in tool_calls])
        response_parts = []
        for fc, result in zip(tool_calls, tool_results):
            response_parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
        return response_parts

    async def _run_loop(
        self, chat_session, current_msg, task_state: Any
    ) -> tuple[defaultdict, list[str], str]:
        turn = 0
        tool_usage_counts = defaultdict(int)
        reasoning_trace = []
        final_answer = ""
        while turn < 50:
            turn += 1
            try:
                full_turn_text, tool_calls = await self._process_turn_stream(chat_session, current_msg, turn, task_state)
            except Exception:
                logger.error("Turn %d Error: %s", turn, traceback.format_exc())
                raise
            if full_turn_text:
                reasoning_trace.append(full_turn_text)
            if not tool_calls:
                if reasoning_trace:
                    final_answer = reasoning_trace.pop()
                break
            current_msg = await self._execute_turn_tools(tool_calls, turn, task_state, tool_usage_counts)
            if turn == 50:
                final_answer = "I've reached the maximum number of steps (50) for this turn."
                await task_state.broadcast(f"event: message\ndata: {json.dumps(final_answer)}\n\n")
        return tool_usage_counts, reasoning_trace, final_answer


class ACPClientHandler(Client):
    """ACP Client to handle streaming updates from Gemini CLI."""

    def __init__(self, task_state, turn_marker: str):
        super().__init__()
        self.task_state = task_state
        self.turn_marker = turn_marker
        self.marker_found = False
        self.tool_usage_counts = defaultdict(int)
        self.reasoning_trace = []
        self.accumulated_raw_text = ""
        self.full_response_text = ""  # Text after the marker
        self.current_text_segment = ""

    def _extract_text(self, content: Any) -> str:
        """Robustly extracts text from various ACP content formats."""
        if content is None: return ""
        if isinstance(content, str): return content
        if isinstance(content, dict):
            return content.get("text") or content.get("thought") or ""
        if isinstance(content, list):
            return "".join(self._extract_text(c) for c in content)
        if hasattr(content, "text") and isinstance(content.text, str):
            return content.text
        if hasattr(content, "thought") and isinstance(content.thought, str):
            return content.thought
        return ""

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        logger.debug("[ACP] Received update type=%s", type(update).__name__)
        
        if isinstance(update, (ToolCallStart, ToolCallProgress)):
            title = getattr(update, "title", None) or getattr(update, "status", None) or "Tool operation"
            if isinstance(update, ToolCallStart) and getattr(update, "title", None):
                self.tool_usage_counts[update.title] += 1
                if self.current_text_segment:
                    self.reasoning_trace.append(self.current_text_segment)
                    self.current_text_segment = ""
            tool_status_msg = f"{title}..."
            await self.task_state.broadcast(f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n")
            return

        chunk_text = ""
        is_thought = False
        is_user_msg = False

        if isinstance(update, AgentMessageChunk):
            chunk_text = self._extract_text(update.content)
        elif isinstance(update, AgentThoughtChunk):
            chunk_text = self._extract_text(update.content)
            is_thought = True
        elif isinstance(update, UserMessageChunk):
            chunk_text = self._extract_text(update.content)
            is_user_msg = True
        
        if not chunk_text:
            return

        logger.debug("[ACP] Chunk text snippet: %s...", chunk_text[:50].replace('\n', '\\n'))

        if not self.marker_found:
            self.accumulated_raw_text += chunk_text
            idx = self.accumulated_raw_text.find(self.turn_marker)
            if idx != -1:
                self.marker_found = True
                logger.info("[ACP] Turn marker found at index %d", idx)
                # Process any text that followed the marker in the same chunk
                new_part = self.accumulated_raw_text[idx + len(self.turn_marker):].lstrip("\n")
                if new_part and not is_user_msg:
                    await self._process_delta(new_part, is_thought)
        else:
            # If marker already found, check if this chunk is a full re-emission or a delta
            if self.turn_marker in chunk_text:
                idx = chunk_text.find(self.turn_marker)
                new_full = chunk_text[idx + len(self.turn_marker):].lstrip("\n")
                delta = new_full[len(self.full_response_text):]
                self.full_response_text = new_full
                if delta and not is_user_msg:
                    await self._process_delta(delta, is_thought)
            else:
                # Treat as delta
                if not is_user_msg:
                    await self._process_delta(chunk_text, is_thought)
                    self.full_response_text += chunk_text

    async def _process_delta(self, delta: str, is_thought: bool):
        logger.debug("[ACP] Processing delta (thought=%s): %s", is_thought, delta[:30].replace('\n', '\\n'))
        self.current_text_segment += delta
        # UI treats all text as messages for now to match SDK engine visibility
        await self.task_state.broadcast(f"event: message\ndata: {json.dumps(delta)}\n\n")

    async def request_permission(self, options: Any, session_id: str, tool_call: Any, **kwargs: Any) -> Any:
        return {"outcome": "approved"}


class CLILLMService(BaseLLMService):
    """Implementation of the LLM service using the Gemini CLI via ACP."""

    async def execute_turn(
        self,
        chat_session: Any,
        current_msg: str,
        task_state: Any,
        turn_context: TurnContext | None = None,
    ) -> tuple[defaultdict, list[str], str]:
        turn_context = turn_context or TurnContext()
        # Use a unique marker to identify where the new response begins
        turn_marker = f"==JULES_TURN_{uuid.uuid4().hex[:8]}=="
        client = ACPClientHandler(task_state, turn_marker)

        try:
            model = await asyncio.to_thread(chat_manager.get_setting, "default_model")
            if not model: model = "gemini-2.0-flash"

            logger.info("[CLI] Starting Gemini process for turn...")
            async with spawn_agent_process(
                client, "gemini", "--acp", "--output-format", "stream-json", "--model", model
            ) as (conn, _proc):
                await conn.initialize(
                    protocol_version=1,
                    client_capabilities=ClientCapabilities(
                        fs=FileSystemCapabilities(read_text_file=True, write_text_file=True),
                        terminal=True,
                    ),
                )

                prompt_msg = current_msg
                if turn_context.is_new_context and turn_context.system_instruction:
                    prompt_msg = f"{turn_context.system_instruction}\n\n{current_msg}"

                prompt_msg = f"{prompt_msg}\n\n{turn_marker}\n\n"

                global ACP_CLI_SESSION_ID
                current_session_id = None
                if ACP_CLI_SESSION_ID:
                    try:
                        await conn.load_session(cwd=git_ops.CODEBASE_ROOT, session_id=ACP_CLI_SESSION_ID, mcp_servers=[])
                        current_session_id = ACP_CLI_SESSION_ID
                    except Exception as e:
                        logger.warning("Failed to load session %s: %s", ACP_CLI_SESSION_ID, e)

                if not current_session_id:
                    session = await conn.new_session(cwd=git_ops.CODEBASE_ROOT, mcp_servers=[])
                    current_session_id = session.session_id
                    ACP_CLI_SESSION_ID = current_session_id

                logger.debug("[CLI] Sending prompt to session %s", current_session_id)
                await conn.prompt(session_id=current_session_id, prompt=[text_block(prompt_msg)])
                logger.info("[CLI] Prompt turn completed.")

        except Exception as e:
            error_str = str(e).lower()
            if "authentication" in error_str or "credentials" in error_str or "missing" in error_str:
                err_msg = "Authentication failed for Gemini CLI. Please run `gemini auth` on your host."
                await task_state.broadcast(f'event: error\ndata: "{err_msg}"\n\n')
                return client.tool_usage_counts, client.reasoning_trace, err_msg
            raise e

        # Finalize segments
        if client.current_text_segment:
            client.reasoning_trace.append(client.current_text_segment)

        final_answer = ""
        if client.reasoning_trace:
            final_answer = client.reasoning_trace.pop()

        return client.tool_usage_counts, client.reasoning_trace, final_answer


def get_llm_service() -> BaseLLMService:
    """Returns the configured LLM service instance."""
    if LLM_ENGINE == "cli":
        return CLILLMService()
    return SDKLLMService()
