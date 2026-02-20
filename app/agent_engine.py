"""
Agent Engine module.
Handles the agent loop and tool execution.
"""

import json
import logging
import traceback
import asyncio
import re
from collections import defaultdict

from google.genai import types

from app.services import git_ops, chat_manager, rag_manager, llm_service

logger = logging.getLogger(__name__)


class TaskState:
    """Manages the state of the active task, including listeners and replay buffer."""

    def __init__(self):
        self.listeners = []
        self.replay_buffer = []
        self.task_handle = asyncio.current_task()

    async def broadcast(self, event: str | None):
        """Broadcasts an event to all listeners and appends to replay buffer."""
        if event is not None:
            self.replay_buffer.append(event)

        # Snapshot listeners to avoid duplicates if a new listener is added during broadcast
        current_listeners = list(self.listeners)
        for queue in current_listeners:
            await queue.put(event)

    def add_listener(self, queue: asyncio.Queue):
        """Adds a new listener and replays buffered events."""
        self.listeners.append(queue)
        for event in self.replay_buffer:
            queue.put_nowait(event)


# Global state for current task
CURRENT_STATE: TaskState | None = None

# Helper for tool map
TOOL_MAP = {
    "list_files": git_ops.list_files,
    "read_file": git_ops.read_file,
    "get_file_history": git_ops.get_file_history,
    "get_recent_commits": git_ops.get_recent_commits,
    "grep_code": git_ops.grep_code,
    "get_file_outline": git_ops.get_file_outline,
    "read_android_manifest": git_ops.read_android_manifest,
    "search_codebase_semantic": rag_manager.search_codebase_semantic,
}


def get_active_stream_queue() -> asyncio.Queue | None:
    """Returns a new queue for the active task stream if it exists."""
    if CURRENT_STATE:
        queue = asyncio.Queue()
        CURRENT_STATE.add_listener(queue)
        return queue
    return None


def _extract_error_message(error_text: str) -> str:
    """Extracts a clean error message from a verbose exception string."""
    # Try to find the inner JSON message key "message"
    # Matches "message": "..." inside the string.
    # Note: This is a heuristic for Gemini API errors wrapped in string reprs.
    match = re.search(r'"message":\s*"(.*?)"', error_text)
    if match:
        return match.group(1)
    return error_text


async def _execute_tool(fc):
    """
    Executes a single tool call safely in a thread.
    Returns the result.
    """
    logger.info("Executing tool: %s args=%s", fc.name, fc.args)
    tool_func = TOOL_MAP.get(fc.name)
    if tool_func:
        try:
            # Tools are synchronous and blocking (e.g. file I/O).
            # Run them in a thread.
            return await asyncio.to_thread(tool_func, **fc.args)
        except Exception as e:  # pylint: disable=broad-exception-caught
            return f"Error executing {fc.name}: {e}"

    # Check MCP tools
    session = llm_service.MCP_TOOL_TO_SESSION_MAP.get(fc.name)
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


def cancel_current_task():
    """Cancels the current running task."""
    if (
        CURRENT_STATE
        and CURRENT_STATE.task_handle
        and not CURRENT_STATE.task_handle.done()
    ):
        logger.info("Cancelling current task...")
        CURRENT_STATE.task_handle.cancel()
        return True
    return False


async def run_agent_task(initial_queue: asyncio.Queue, chat_session, user_msg: str):
    """
    Background worker that runs the agent loop and pushes events to the queue.
    Decoupled from the HTTP response to ensure completion even if client disconnects.
    """
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements, too-many-nested-blocks, global-statement
    global CURRENT_STATE
    task_state = TaskState()
    CURRENT_STATE = task_state
    task_state.add_listener(initial_queue)

    current_msg = user_msg
    turn = 0
    tool_usage_counts = defaultdict(int)
    reasoning_trace = []
    final_answer = ""

    try:
        while turn < 30:
            turn += 1
            tool_calls = []
            logger.debug("[TURN %d] Sending message to SDK", turn)

            turn_text_parts = []

            try:
                # Use native async method for streaming with retry logic
                max_retries = 3
                retry_delay = 2
                stream = None

                for attempt in range(max_retries + 1):
                    try:
                        stream = await chat_session.send_message_stream(current_msg)
                        break  # Success
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
                            raise e  # Re-raise if not retryable or max retries reached

                if not stream:
                    raise RuntimeError("Failed to establish stream after retries.")

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
                        logger.error(
                            "[TURN %d] Error processing chunk text: %s", turn, e
                        )

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
                        logger.error(
                            "[TURN %d] Error processing chunk tool calls: %s", turn, e
                        )

                # End of stream for this turn.
                full_turn_text = "".join(turn_text_parts)

                if full_turn_text:
                    reasoning_trace.append(full_turn_text)

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Turn %d Error: %s", turn, traceback.format_exc())
                error_msg = _extract_error_message(str(e))
                await task_state.broadcast(
                    f"event: error\ndata: {json.dumps(error_msg)}\n\n"
                )
                return

            # Decision Point
            if not tool_calls:
                if reasoning_trace:
                    final_answer = reasoning_trace.pop()
                break

            # Execute Tools
            logger.debug("[TURN %d] Executing tools...", turn)
            tool_descriptions = []
            for fc in tool_calls:
                tool_usage_counts[fc.name] += 1
                if fc.name == "read_file":
                    tool_descriptions.append(
                        f"Reading file '{fc.args.get('filepath')}'"
                    )
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
                else:
                    tool_descriptions.append(f"Running {fc.name}")

            joined_descriptions = ", ".join(tool_descriptions)
            # STRICT JSON ENCODING prevents newlines from breaking SSE
            tool_status_msg = f"{joined_descriptions}..."
            await task_state.broadcast(
                f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n"
            )

            # Parallel Execution
            tool_results = await asyncio.gather(
                *[_execute_tool(fc) for fc in tool_calls]
            )

            response_parts = []
            for fc, result in zip(tool_calls, tool_results):
                response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": result}
                    )
                )

            # Update State
            current_msg = response_parts

        # Construct Summary
        stream_summary_markdown = ""

        if tool_usage_counts or reasoning_trace:
            # pylint: disable=line-too-long
            stream_summary_markdown = "\n\n<details><summary>Click to view reasoning and tool usage</summary>\n\n"
            # pylint: enable=line-too-long

            # Tool Usage
            if tool_usage_counts:
                stream_summary_markdown += "#### Tool Usage\n"
                for tool, count in tool_usage_counts.items():
                    stream_summary_markdown += f"- **{tool}**: {count}\n"
                stream_summary_markdown += "\n"

            # Reasoning Trace
            if reasoning_trace:
                stream_summary_markdown += "#### Reasoning Trace\n"
                for i, step in enumerate(reasoning_trace, 1):
                    stream_summary_markdown += f"{i}. {step}\n\n"

            stream_summary_markdown += "</details>"

            await task_state.broadcast(
                f"event: message\ndata: {json.dumps(stream_summary_markdown)}\n\n"
            )

        # Construct History Summary (includes Final Answer + Details)
        history_summary = ""
        if final_answer:
            history_summary += final_answer

        if stream_summary_markdown:
            history_summary += stream_summary_markdown

        # Save to history ONLY at the very end
        if history_summary:
            await asyncio.to_thread(chat_manager.save_message, "model", history_summary)

        await task_state.broadcast("event: done\ndata: [DONE]\n\n")

    except asyncio.CancelledError:
        logger.info("Task was cancelled.")
        await task_state.broadcast(
            'event: error\ndata: "Task was cancelled by user."\n\n'
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Worker Error: %s", traceback.format_exc())
        error_msg = _extract_error_message(str(e))
        await task_state.broadcast(f"event: error\ndata: {json.dumps(error_msg)}\n\n")
    finally:
        CURRENT_STATE = None
        # Signal end of queue
        await task_state.broadcast(None)
        logger.info("Background worker finished.")
