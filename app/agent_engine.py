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


from app.services import chat_manager, llm_service

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


async def _finalize_task(
    tool_usage_counts: defaultdict,
    reasoning_trace: list[str],
    final_answer: str,
    task_state: TaskState,
) -> None:
    """
    Constructs the final summary, saves to history, and signals completion.
    """
    # Construct Summary
    stream_summary_markdown = ""

    if tool_usage_counts or reasoning_trace:
        # pylint: disable=line-too-long
        stream_summary_markdown = (
            "\n\n<details><summary>Click to view reasoning and tool usage</summary>\n\n"
        )
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


def cancel_current_task() -> bool:
    """Cancels the currently running agent task, if any."""
    if (
        CURRENT_STATE
        and CURRENT_STATE.task_handle
        and not CURRENT_STATE.task_handle.done()
    ):
        CURRENT_STATE.task_handle.cancel()
        return True
    return False


async def run_agent_task(
    initial_queue: asyncio.Queue,
    chat_session,
    user_msg: str,
    turn_context: llm_service.TurnContext | None = None,
):
    """
    Background worker that runs the agent loop and pushes events to the queue.
    Decoupled from the HTTP response to ensure completion even if client disconnects.
    """
    # pylint: disable=global-statement
    global CURRENT_STATE
    task_state = TaskState()
    CURRENT_STATE = task_state
    task_state.add_listener(initial_queue)

    try:
        service = llm_service.get_llm_service()
        tool_usage_counts, reasoning_trace, final_answer = await service.execute_turn(
            chat_session, user_msg, task_state, turn_context
        )
        await _finalize_task(
            tool_usage_counts, reasoning_trace, final_answer, task_state
        )

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
