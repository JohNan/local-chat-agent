"""
Tests for the web search configuration in ChatRequest.
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from google.genai import types

# Ensure app is importable
sys.path.append(os.getcwd())

from app.main import app  # pylint: disable=wrong-import-position
from app import agent_engine


@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    return TestClient(app)


def test_web_search_enabled_via_request(client):
    """Test that include_web_search=True enables google_search."""
    with patch("app.routers.chat.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock stream response
        async def mock_stream(*args, **kwargs):
            yield MagicMock(text="Hello", parts=[])

        mock_chat.send_message_stream = MagicMock(side_effect=mock_stream)

        # Send request with include_web_search=True
        response = client.post(
            "/chat",
            json={"message": "Search for something", "include_web_search": True},
        )

        assert response.status_code == 200

        # Check call args to aio.chats.create
        _, kwargs = mock_client.aio.chats.create.call_args
        config = kwargs["config"]

        # Verify tool has google_search
        assert len(config.tools) == 1
        tool = config.tools[0]
        assert tool.google_search is not None
        assert isinstance(tool.google_search, types.GoogleSearch)

        # Verify system instruction includes search prompt
        assert agent_engine.SYSTEM_INSTRUCTION in config.system_instruction
        assert "access to Google Search" in config.system_instruction


def test_web_search_disabled_via_request(client):
    """Test that include_web_search=False disables google_search."""
    with patch("app.routers.chat.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock stream response
        async def mock_stream(*args, **kwargs):
            yield MagicMock(text="Hello", parts=[])

        mock_chat.send_message_stream = MagicMock(side_effect=mock_stream)

        # Send request with include_web_search=False
        response = client.post(
            "/chat", json={"message": "Hello", "include_web_search": False}
        )

        assert response.status_code == 200

        # Check call args
        _, kwargs = mock_client.aio.chats.create.call_args
        config = kwargs["config"]

        # Verify tool has NO google_search (it should be None)
        assert len(config.tools) == 1
        tool = config.tools[0]
        assert tool.google_search is None

        # Verify system instruction is default
        assert config.system_instruction == agent_engine.SYSTEM_INSTRUCTION


def test_web_search_default_false(client):
    """Test that default (None) falls back to env var (False)."""
    with patch("app.routers.chat.CLIENT") as mock_client, patch(
        "app.routers.chat.ENABLE_GOOGLE_SEARCH", False
    ):

        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock stream response
        async def mock_stream(*args, **kwargs):
            yield MagicMock(text="Hello", parts=[])

        mock_chat.send_message_stream = MagicMock(side_effect=mock_stream)

        # Send request without include_web_search
        response = client.post("/chat", json={"message": "Hello"})

        assert response.status_code == 200

        _, kwargs = mock_client.aio.chats.create.call_args
        config = kwargs["config"]

        # Verify tool has NO google_search
        tool = config.tools[0]
        assert tool.google_search is None


def test_web_search_env_var_true(client):
    """Test that env var ENABLE_GOOGLE_SEARCH=True enables search if request is None."""
    with patch("app.routers.chat.CLIENT") as mock_client, patch(
        "app.routers.chat.ENABLE_GOOGLE_SEARCH", True
    ):

        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock stream response
        async def mock_stream(*args, **kwargs):
            yield MagicMock(text="Hello", parts=[])

        mock_chat.send_message_stream = MagicMock(side_effect=mock_stream)

        response = client.post("/chat", json={"message": "Hello"})

        assert response.status_code == 200

        _, kwargs = mock_client.aio.chats.create.call_args
        config = kwargs["config"]

        # Verify tool HAS google_search
        tool = config.tools[0]
        assert tool.google_search is not None
