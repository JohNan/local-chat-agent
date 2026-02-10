import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from app import agent_engine
from google.genai import types


@pytest.mark.asyncio
async def test_summary_injection():
    # Mock queue
    queue = asyncio.Queue()

    # Mock chat session
    chat_session = MagicMock()

    # Mock stream response
    async def mock_stream():
        # First chunk: text
        chunk1 = MagicMock()
        chunk1.text = "Here is the plan."
        chunk1.parts = [types.Part(text="Here is the plan.")]
        yield chunk1

        # Second chunk: tool call
        chunk2 = MagicMock()
        chunk2.text = None
        chunk2.parts = [
            types.Part(
                function_call=types.FunctionCall(
                    name="list_files", args={"directory": "."}
                )
            )
        ]
        yield chunk2

    chat_session.send_message_stream.return_value = mock_stream()

    # Mock tool execution
    original_tool_map = agent_engine.TOOL_MAP
    agent_engine.TOOL_MAP = {"list_files": lambda **kwargs: ["file1.txt", "file2.txt"]}

    try:
        # Run agent task (limit turns to avoid infinite loop if logic is broken)
        # We need to simulate the loop finishing.
        # The loop breaks if no tool calls.
        # But here we have a tool call. So it will loop again.
        # We need the second turn to produce no tool calls.

        call_count = 0

        async def turn_1_stream():
            chunk1 = MagicMock()
            chunk1.text = "Thinking..."
            chunk1.parts = [types.Part(text="Thinking...")]
            yield chunk1

            chunk2 = MagicMock()
            chunk2.text = None
            chunk2.parts = [
                types.Part(
                    function_call=types.FunctionCall(
                        name="list_files", args={"directory": "."}
                    )
                )
            ]
            yield chunk2

        async def turn_2_stream():
            chunk3 = MagicMock()
            chunk3.text = "Done."
            chunk3.parts = [types.Part(text="Done.")]
            yield chunk3

        async def mock_send_message_stream(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return turn_1_stream()
            else:
                return turn_2_stream()

        chat_session.send_message_stream = mock_send_message_stream

        await agent_engine.run_agent_task(queue, chat_session, "user message")

        # Collect all messages from queue
        messages = []
        while not queue.empty():
            msg = await queue.get()
            if msg is None:
                break
            messages.append(msg)

        # Verify summary exists
        summary_found = False
        for msg in messages:
            if "Click to view reasoning and tool usage" in msg:
                summary_found = True
                # Check content
                assert "#### Tool Usage" in msg
                assert "**list_files**: 1" in msg
                assert "#### Reasoning Trace" in msg
                assert "Thinking..." in msg
                assert "Done." in msg

        assert summary_found, "Summary message not found in queue output"

    finally:
        agent_engine.TOOL_MAP = original_tool_map
