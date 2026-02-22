"""
Tests for code execution tool alias handling.
"""

from unittest.mock import MagicMock, patch, AsyncMock
from tests.utils import AsyncIterator
import app.agent_engine
from app.services import code_executor


def test_tool_map_alias():
    """Verify that run_programming_task maps to code_executor.execute_code."""
    assert "run_programming_task" in app.agent_engine.TOOL_MAP
    assert (
        app.agent_engine.TOOL_MAP["run_programming_task"] == code_executor.execute_code
    )


def test_run_programming_task_logging(client):
    """Test that run_programming_task is executed and logged correctly."""
    with patch("app.routers.chat.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock chunk with run_programming_task tool call
        chunk1 = MagicMock()
        chunk1.text = ""

        fc1 = MagicMock()
        fc1.name = "run_programming_task"
        fc1.args = {"code": "print('hello')"}

        part1 = MagicMock()
        part1.text = None
        part1.function_call = fc1

        chunk1.parts = [part1]
        chunk1.function_calls = [fc1]

        # Final response chunk
        chunk2 = MagicMock()
        chunk2.text = "Code executed"
        part2 = MagicMock()
        part2.text = "Code executed"
        part2.function_call = None
        chunk2.parts = [part2]
        chunk2.function_calls = []

        # Mock send_message_stream
        mock_chat.send_message_stream = AsyncMock(
            side_effect=[AsyncIterator([chunk1]), AsyncIterator([chunk2])]
        )

        # We rely on the real TOOL_MAP.
        # This means the test will FAIL if run_programming_task is missing from TOOL_MAP.

        response = client.get("/chat?message=run code")

        assert response.status_code == 200
        data = response.text

        # Verify output contains tool execution logs
        assert "event: tool" in data
        # This assertion checks the logging logic I need to add
        # If not implemented, it would log "Running run_programming_task"
        assert "Running python code" in data
