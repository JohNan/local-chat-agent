"""
Tests for multimodal support.
"""

from unittest.mock import MagicMock, patch, AsyncMock
import base64
from google.genai import types
from tests.utils import AsyncIterator
from app import main


def test_format_history_with_image():
    """Test formatting of history containing images (inline_data)."""
    # Mock base64 image data
    image_data = b"fake_image_data"
    encoded_image = base64.b64encode(image_data).decode("utf-8")

    history = [
        {
            "role": "user",
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": encoded_image,
                    }
                },
                {"text": "Describe this image"},
            ],
        },
        {"role": "model", "parts": [{"text": "It's a cat."}]},
        # Current message (will be excluded by _format_history)
        {"role": "user", "parts": [{"text": "Next message"}]},
    ]

    formatted = main._format_history(history)

    assert len(formatted) == 2
    parts = formatted[0]["parts"]
    assert len(parts) == 2

    # Check image part
    part0 = parts[0]
    assert hasattr(part0, "inline_data")
    assert part0.inline_data.mime_type == "image/png"
    assert part0.inline_data.data == image_data

    # Check text part
    assert parts[1].text == "Describe this image"


def test_chat_endpoint_with_media(client):
    """Test chat endpoint with media payload."""
    # Mock base64 image data
    image_data = b"fake_image_data"
    encoded_image = base64.b64encode(image_data).decode("utf-8")

    payload = {
        "message": "Describe this image",
        "media": [{"mime_type": "image/png", "data": encoded_image}],
    }

    with patch("app.main.CLIENT") as mock_client:
        mock_chat = MagicMock()
        mock_client.aio.chats.create.return_value = mock_chat

        # Mock chunk
        mock_chunk = MagicMock()
        mock_chunk.text = "This is an image description"
        part = MagicMock()
        part.text = "This is an image description"
        part.function_call = None
        mock_chunk.parts = [part]
        mock_chunk.function_calls = []

        # Mock stream
        mock_chat.send_message_stream = AsyncMock(
            return_value=AsyncIterator([mock_chunk])
        )

        response = client.post("/chat", json=payload)

        assert response.status_code == 200

        # Consume response
        content = response.text

        mock_chat.send_message_stream.assert_called_once()
        args, _ = mock_chat.send_message_stream.call_args
        message_arg = args[0]

        # message_arg should be a list of parts
        assert isinstance(message_arg, list)
        assert len(message_arg) == 2
        # First part: image
        assert message_arg[0].inline_data.mime_type == "image/png"
        assert message_arg[0].inline_data.data == image_data
        # Second part: text
        assert message_arg[1].text == "Describe this image"
