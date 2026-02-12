"""
Tests for the chat streaming functionality.
"""

from unittest.mock import MagicMock, patch, AsyncMock
from google.genai import types
from tests.utils import AsyncIterator


def test_chat_get_stream_basic(client):
    """Test basic chat streaming with GET request."""
    # Mock the Gemini Client
    with patch("app.main.CLIENT") as mock_client:
        # Mock CLIENT.aio.chats.create to be synchronous returning mock_chat
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock chunk
        mock_chunk = MagicMock()
        mock_chunk.text = "Hello world"
        mock_chunk.parts = []
        mock_chunk.function_calls = []

        # Mock the stream iterator
        # send_message_stream must be awaitable and return an async iterator
        async def mock_send_message_stream(*args, **kwargs):
            return AsyncIterator([mock_chunk])

        mock_chat.send_message_stream = mock_send_message_stream

        # Test GET request
        response = client.get("/chat?message=Hi")

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        data = response.text
        print(f"DEBUG: Response data:\n{data}")

        # Check for message event
        assert "event: message" in data
        # Check for JSON encoded text
        assert 'data: "Hello world"' in data
        # Check for done event
        assert "event: done" in data
        assert "data: [DONE]" in data


def test_chat_tool_execution(client):
    """Test chat streaming with tool execution."""
    with patch("app.main.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Setup mock chunks for 2 turns
        # Turn 1: Tool Call
        chunk1 = MagicMock()
        chunk1.text = ""
        fc = MagicMock()
        fc.name = "list_files"
        fc.args = {"directory": "."}
        part1 = MagicMock()
        part1.function_call = fc
        chunk1.parts = [part1]
        chunk1.function_calls = [fc]

        # Turn 2: Final Response
        chunk2 = MagicMock()
        chunk2.text = "Here are the files"
        chunk2.parts = []
        chunk2.function_calls = []

        # Mock the stream iterator for two calls
        # We need side_effect behavior for async function

        # We can't easily use side_effect on an async def function directly if we want different return values
        # So we create a mock that returns the side effects

        mock_chat.send_message_stream = AsyncMock(
            side_effect=[AsyncIterator([chunk1]), AsyncIterator([chunk2])]
        )

        # Mock the tool function itself to avoid actual git ops
        dummy_fd = types.FunctionDeclaration(name="dummy", description="dummy")
        with patch(
            "app.services.git_ops.list_files", return_value=["file1.txt"]
        ), patch(
            "google.genai.types.FunctionDeclaration.from_callable",
            return_value=dummy_fd,
        ):
            response = client.get("/chat?message=list files")

            assert response.status_code == 200
            data = response.text
            print(f"DEBUG: Tool Response data:\n{data}")

            # Check for tool event
            assert "event: tool" in data
            # Check for strict JSON encoded tool message
            assert "Listing directory '.'..." in data

            # Check for final message
            assert "event: message" in data
            assert 'data: "Here are the files"' in data

            # Check for done
            assert "event: done" in data
