"""
Tests for parallel tool execution in agent engine.
"""

import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.append(os.getcwd())

from app.main import app  # pylint: disable=wrong-import-position


@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    return TestClient(app)


class AsyncIterator:
    """Helper to create an async iterator from a list."""

    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self.iter = iter(self.items)  # pylint: disable=attribute-defined-outside-init
        return self

    async def __anext__(self):
        try:
            return next(self.iter)
        except StopIteration as e:
            raise StopAsyncIteration from e


def test_parallel_tool_execution(client):
    """Test that multiple tools are executed in parallel."""
    with patch("app.main.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock chunk with 2 tool calls
        chunk1 = MagicMock()
        chunk1.text = ""

        fc1 = MagicMock()
        fc1.name = "read_file"
        fc1.args = {"filepath": "file1.txt"}

        fc2 = MagicMock()
        fc2.name = "list_files"
        fc2.args = {"directory": "."}

        part1 = MagicMock()
        part1.text = None
        part1.function_call = fc1
        part2 = MagicMock()
        part2.text = None
        part2.function_call = fc2

        chunk1.parts = [part1, part2]
        chunk1.function_calls = [fc1, fc2]

        # Final response chunk
        chunk2 = MagicMock()
        chunk2.text = "Here is the content and list"
        part3 = MagicMock()
        part3.text = "Here is the content and list"
        part3.function_call = None
        chunk2.parts = [part3]
        chunk2.function_calls = []

        # Mock send_message_stream
        mock_chat.send_message_stream = AsyncMock(
            side_effect=[AsyncIterator([chunk1]), AsyncIterator([chunk2])]
        )

        # Mock the actual tool implementations with delays to simulate work
        # and verify concurrency (though difficult to prove in unit test, we can check calls)

        # Note: The real tools are synchronous, but asyncio.to_thread handles them.
        # We can mock them as synchronous functions.

        mock_read_impl = MagicMock(return_value="Content of file1.txt")
        mock_list_impl = MagicMock(return_value=["file1.txt", "file2.txt"])

        # Patch the tools in TOOL_MAP directly because agent_engine imports them at module level
        # so patching git_ops directly doesn't update TOOL_MAP
        with patch.dict(
            "app.agent_engine.TOOL_MAP",
            {"read_file": mock_read_impl, "list_files": mock_list_impl},
        ):

            response = client.get("/chat?message=do both")

            assert response.status_code == 200
            data = response.text

            # Verify both tools were called
            mock_read_impl.assert_called_once_with(filepath="file1.txt")
            mock_list_impl.assert_called_once_with(directory=".")

            # Verify output contains tool execution logs
            assert "event: tool" in data
            assert "Reading file 'file1.txt'" in data
            assert "Listing directory '.'" in data

            # Verify final response
            assert "event: message" in data
            assert 'data: "Here is the content and list"' in data

            # Check persistence calls (optional, but good)
            # We can't easily check save_message calls unless we patch chat_manager
