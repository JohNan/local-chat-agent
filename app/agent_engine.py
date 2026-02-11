"""
Agent Engine module.
Handles the agent loop and tool execution.
"""

import json
import logging
import traceback
import asyncio
from collections import defaultdict

from google.genai import types

from app.services import git_ops, chat_manager

logger = logging.getLogger(__name__)

# Global queue for current task
CURRENT_TASK_QUEUE = None
CURRENT_TASK: asyncio.Task | None = None

# Helper for tool map
TOOL_MAP = {
    "list_files": git_ops.list_files,
    "read_file": git_ops.read_file,
    "get_file_history": git_ops.get_file_history,
    "get_recent_commits": git_ops.get_recent_commits,
    "grep_code": git_ops.grep_code,
    "get_file_outline": git_ops.get_file_outline,
    "read_android_manifest": git_ops.read_android_manifest,
}

SYSTEM_INSTRUCTION = (
    "Technical Lead Agent\n"
    "You are the Technical Lead and Prompt Architect. "
    "You have **READ-ONLY** access to the user's codebase.\n\n"
    "**CRITICAL RULES:**\n"
    "1. **Explore First:** When the user asks a question, "
    "you must **IMMEDIATELY** use `list_files`, `grep_code`, or `read_file` to investigate. "
    "**NEVER** ask the user for file paths or code snippets. Find them yourself.\n"
    "2. **Debug with History:** If analyzing a bug or regression, "
    "use `get_file_history` to understand recent changes and intent before suggesting a fix.\n"
    "3. **Read-Only:** You cannot edit, write, or delete files. "
    "If code changes are required, you must describe them or generate a 'Jules Prompt'.\n"
    '4. **Jules Prompt:** When the user asks to "write a prompt", "deploy", '
    'or "create instructions", you must generate a structured block starting with '
    "`## Jules Prompt` containing the specific context and acceptance criteria. "
    "Every Jules Prompt MUST explicitly instruct the agent to: "
    "'First, read the `AGENTS.md` file to understand the project architecture "
    "and development rules before starting any implementation.'\n"
    "5. **Visualizing Compose UI:** When analyzing Jetpack Compose code, use `get_file_outline` to "
    "identify `@Composable` functions. Treat the nesting of these function calls "
    "(found via `grep_code`) as the visual component tree.\n"
    "6. **Android Configuration:** Always read `AndroidManifest.xml` first to identify "
    "the application entry point and required permissions.\n"
    "7. **Transparency:** Before executing a tool, you must briefly explain your plan to the user. "
    "For example: 'I will search for the `User` class to understand the schema.' "
    "This keeps the user informed of your reasoning.\n"
    "8. **Self-Correction:** If a tool returns an error (e.g., file not found), "
    "read the error message carefully and try to fix the path or arguments before giving up.\n\n"
    "Note: `read_file` automatically truncates large files. If you need to read the rest, "
    "use the `start_line` parameter."
)


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
    else:
        logger.warning("Unknown tool call: %s", fc.name)
        return f"Error: Tool {fc.name} not found."


def cancel_current_task():
    """Cancels the current running task."""
    if CURRENT_TASK and not CURRENT_TASK.done():
        logger.info("Cancelling current task...")
        CURRENT_TASK.cancel()
        return True
    return False


async def run_agent_task(queue: asyncio.Queue, chat_session, user_msg: str):
    """
    Background worker that runs the agent loop and pushes events to the queue.
    Decoupled from the HTTP response to ensure completion even if client disconnects.
    """
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements, too-many-nested-blocks, global-statement
    global CURRENT_TASK_QUEUE, CURRENT_TASK
    CURRENT_TASK_QUEUE = queue
    CURRENT_TASK = asyncio.current_task()
    current_msg = user_msg
    turn = 0
    tool_usage_counts = defaultdict(int)
    reasoning_trace = []

    try:
        while turn < 30:
            turn += 1
            tool_calls = []
            logger.debug("[TURN %d] Sending message to SDK", turn)

            turn_text_parts = []

            try:
                # Use native async method for streaming
                stream = await chat_session.send_message_stream(current_msg)

                async for chunk in stream:
                    # Text processing
                    try:
                        if chunk.text:
                            turn_text_parts.append(chunk.text)
                            await queue.put(
                                f"event: message\ndata: {json.dumps(chunk.text)}\n\n"
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
                # Immediate Persistence: Save the text generated in this turn.
                full_turn_text = "".join(turn_text_parts)
                if full_turn_text:
                    chat_manager.save_message("model", full_turn_text)
                    reasoning_trace.append(full_turn_text)

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Turn %d Error: %s", turn, traceback.format_exc())
                await queue.put(f"event: error\ndata: {json.dumps(str(e))}\n\n")
                return

            # Decision Point
            if not tool_calls:
                if reasoning_trace:
                    reasoning_trace.pop()
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
                else:
                    tool_descriptions.append(f"Running {fc.name}")

            joined_descriptions = ", ".join(tool_descriptions)
            # STRICT JSON ENCODING prevents newlines from breaking SSE
            tool_status_msg = f"{joined_descriptions}..."
            await queue.put(f"event: tool\ndata: {json.dumps(tool_status_msg)}\n\n")

            # Parallel Execution
            tool_results = await asyncio.gather(
                *[_execute_tool(fc) for fc in tool_calls]
            )

            response_parts = []
            for fc, result in zip(tool_calls, tool_results):
                # Immediate Persistence: Save tool output
                # Using 'function' role to denote tool output, preserving it in history
                # Run in thread to avoid blocking loop
                await asyncio.to_thread(
                    chat_manager.save_message,
                    "function",
                    str(result),
                    parts=[
                        {
                            "text": str(result),
                            "functionResponse": {
                                "name": fc.name,
                                "response": {"result": result},
                            },
                        }
                    ],
                )

                response_parts.append(
                    types.Part.from_function_response(
                        name=fc.name, response={"result": result}
                    )
                )

            # Update State
            current_msg = response_parts

        # Construct Summary
        if tool_usage_counts or reasoning_trace:
            # pylint: disable=line-too-long
            summary_markdown = "\n\n<details><summary>Click to view reasoning and tool usage</summary>\n\n"
            # pylint: enable=line-too-long

            # Tool Usage
            if tool_usage_counts:
                summary_markdown += "#### Tool Usage\n"
                for tool, count in tool_usage_counts.items():
                    summary_markdown += f"- **{tool}**: {count}\n"
                summary_markdown += "\n"

            # Reasoning Trace
            if reasoning_trace:
                summary_markdown += "#### Reasoning Trace\n"
                for i, step in enumerate(reasoning_trace, 1):
                    summary_markdown += f"{i}. {step}\n\n"

            summary_markdown += "</details>"

            await queue.put(f"event: message\ndata: {json.dumps(summary_markdown)}\n\n")

        await queue.put("event: done\ndata: [DONE]\n\n")

    except asyncio.CancelledError:
        logger.info("Task was cancelled.")
        await queue.put('event: error\ndata: "Task was cancelled by user."\n\n')
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Worker Error: %s", traceback.format_exc())
        await queue.put(f"event: error\ndata: {json.dumps(str(e))}\n\n")
    finally:
        CURRENT_TASK_QUEUE = None
        CURRENT_TASK = None
        # Signal end of queue
        await queue.put(None)
        logger.info("Background worker finished.")
