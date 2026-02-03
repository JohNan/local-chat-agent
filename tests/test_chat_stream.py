import sys
import os
import json
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.append(os.getcwd())

# Import app directly from main
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_chat_get_stream_basic(client):
    # Mock the Gemini Client
    with patch("app.main.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.chats.create.return_value = mock_chat

        # Mock chunk
        mock_chunk = MagicMock()
        mock_chunk.text = "Hello world"
        mock_chunk.parts = []

        # Mock the stream iterator
        mock_chat.send_message_stream.return_value = iter([mock_chunk])

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
    with patch("app.main.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.chats.create.return_value = mock_chat

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

        # Turn 2: Final Response
        chunk2 = MagicMock()
        chunk2.text = "Here are the files"
        chunk2.parts = []

        # Mock the stream iterator for two calls
        mock_chat.send_message_stream.side_effect = [iter([chunk1]), iter([chunk2])]

        # Mock the tool function itself to avoid actual git ops
        with patch("app.services.git_ops.list_files", return_value=["file1.txt"]):
            response = client.get("/chat?message=list files")

            assert response.status_code == 200
            data = response.text
            print(f"DEBUG: Tool Response data:\n{data}")

            # Check for tool event
            assert "event: tool" in data
            # Check for strict JSON encoded tool message
            # The tool message is: 🛠 Listing directory '.'...
            # JSON encoded: "🛠 Listing directory '.'..."
            # In the stream: data: "..."
            assert "Listing directory '.'" in data

            # Check for final message
            assert "event: message" in data
            assert 'data: "Here are the files"' in data

            # Check for done
            assert "event: done" in data
