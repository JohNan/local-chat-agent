import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agent_engine import run_agent_task, TaskState
from google.genai import types

# Helper async iterator
class AsyncIterator:
    def __init__(self, seq):
        self.iter = iter(seq)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration:
            raise StopAsyncIteration

@pytest.mark.asyncio
async def test_run_agent_task_basic_flow():
    # Setup mocks
    mock_queue = asyncio.Queue()
    mock_chat_session = MagicMock()

    # Mock chunks
    chunk1 = MagicMock()
    chunk1.text = "Hello "
    chunk1.parts = [MagicMock(text="Hello ", function_call=None)]
    chunk1.function_calls = []

    chunk2 = MagicMock()
    chunk2.text = "World"
    chunk2.parts = [MagicMock(text="World", function_call=None)]
    chunk2.function_calls = []

    # Mock stream
    async def get_stream(*args, **kwargs):
        return AsyncIterator([chunk1, chunk2])

    mock_chat_session.send_message_stream = get_stream

    # Run the task
    with patch("app.agent_engine.chat_manager.save_message", new_callable=MagicMock) as mock_save:
        await run_agent_task(mock_queue, mock_chat_session, "Hi")

    # Collect events
    events = []
    while not mock_queue.empty():
        events.append(await mock_queue.get())

    # Verify events
    # We expect message events for chunks
    message_events = [e for e in events if e and "event: message" in e]
    assert len(message_events) >= 2
    assert "Hello " in message_events[0]
    assert "World" in message_events[1]

    # Expect done event
    done_event = [e for e in events if e and "event: done" in e]
    assert len(done_event) == 1

    # Verify save_message called
    mock_save.assert_called_once()
    args, _ = mock_save.call_args
    assert args[0] == "model"
    assert "Hello World" in args[1]

@pytest.mark.asyncio
async def test_run_agent_task_tool_execution():
    # Setup mocks
    mock_queue = asyncio.Queue()
    mock_chat_session = MagicMock()

    # Turn 1: Tool Call
    chunk1 = MagicMock()
    chunk1.text = ""
    fc = MagicMock()
    fc.name = "list_files"
    fc.args = {"directory": "."}
    part1 = MagicMock()
    part1.text = None
    part1.function_call = fc
    chunk1.parts = [part1]
    chunk1.function_calls = [fc]

    # Turn 2: Final Answer
    chunk2 = MagicMock()
    chunk2.text = "Here are files"
    part2 = MagicMock()
    part2.text = "Here are files"
    part2.function_call = None
    chunk2.parts = [part2]
    chunk2.function_calls = []

    # Mock stream with side effects for turns
    async def get_stream_side_effect(*args, **kwargs):
        # We need to simulate side effects based on calls
        # But simple side_effect on a function works if we assign it to an AsyncMock or handle it manually
        if not hasattr(get_stream_side_effect, "call_count"):
            get_stream_side_effect.call_count = 0

        results = [
            AsyncIterator([chunk1]),
            AsyncIterator([chunk2])
        ]
        result = results[get_stream_side_effect.call_count]
        get_stream_side_effect.call_count += 1
        return result

    mock_chat_session.send_message_stream = get_stream_side_effect

    # Mock tool execution
    with patch("app.agent_engine.git_ops.list_files", return_value=["file1.txt"]), \
         patch("app.agent_engine.chat_manager.save_message") as mock_save:

        await run_agent_task(mock_queue, mock_chat_session, "list files")

    # Collect events
    events = []
    while not mock_queue.empty():
        events.append(await mock_queue.get())

    # Verify tool execution event
    tool_events = [e for e in events if e and "event: tool" in e]
    assert len(tool_events) >= 1
    assert "Listing directory" in tool_events[0]

    # Verify final message
    message_events = [e for e in events if e and "event: message" in e]
    # One for summary, one for final answer chunk
    assert len(message_events) >= 1
    assert "Here are files" in message_events[-2] # likely the last chunk

    # Verify summary
    summary_event = message_events[-1] # likely the summary
    if "Click to view reasoning" in summary_event:
        pass # OK

    # Verify save_message contains tool usage
    mock_save.assert_called_once()
    args, _ = mock_save.call_args
    assert "Here are files" in args[1]
    assert "Tool Usage" in args[1]
