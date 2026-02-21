"""
Tests for the prepare_messages function in llm_service.
"""
import base64
import sys
import os
import pytest

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import llm_service


class TestPrepareMessages:
    """Test suite for prepare_messages function."""

    def test_text_only(self):
        """Test with text only input."""
        user_msg = "Hello, world!"
        media = []

        storage_parts, gemini_msg = llm_service.prepare_messages(user_msg, media)

        # Verify storage_parts
        assert len(storage_parts) == 1
        assert storage_parts[0] == {"text": user_msg}

        # Verify gemini_msg
        assert len(gemini_msg) == 1
        assert gemini_msg[0].text == user_msg

    def test_media_only(self):
        """Test with media only input."""
        user_msg = ""
        # Create a small dummy image
        dummy_data = b"fake_image_data"
        encoded_data = base64.b64encode(dummy_data).decode("utf-8")
        media = [{"mime_type": "image/png", "data": encoded_data}]

        storage_parts, gemini_msg = llm_service.prepare_messages(user_msg, media)

        # Verify storage_parts
        assert len(storage_parts) == 1
        assert storage_parts[0]["inline_data"]["mime_type"] == "image/png"
        assert storage_parts[0]["inline_data"]["data"] == encoded_data

        # Verify gemini_msg
        assert len(gemini_msg) == 1
        assert gemini_msg[0].inline_data.mime_type == "image/png"
        assert gemini_msg[0].inline_data.data == dummy_data

    def test_text_and_media(self):
        """Test with both text and media input."""
        user_msg = "Look at this image"
        dummy_data = b"fake_image_data"
        encoded_data = base64.b64encode(dummy_data).decode("utf-8")
        media = [{"mime_type": "image/jpeg", "data": encoded_data}]

        storage_parts, gemini_msg = llm_service.prepare_messages(user_msg, media)

        # Verify storage_parts
        assert len(storage_parts) == 2
        assert storage_parts[0] == {"text": user_msg}
        assert storage_parts[1]["inline_data"]["mime_type"] == "image/jpeg"
        assert storage_parts[1]["inline_data"]["data"] == encoded_data

        # Verify gemini_msg
        assert len(gemini_msg) == 2
        assert gemini_msg[0].text == user_msg
        assert gemini_msg[1].inline_data.mime_type == "image/jpeg"
        assert gemini_msg[1].inline_data.data == dummy_data

    def test_multiple_media(self):
        """Test with multiple media items."""
        user_msg = "Two images"
        dummy_data1 = b"image1"
        encoded_data1 = base64.b64encode(dummy_data1).decode("utf-8")
        dummy_data2 = b"image2"
        encoded_data2 = base64.b64encode(dummy_data2).decode("utf-8")

        media = [
            {"mime_type": "image/png", "data": encoded_data1},
            {"mime_type": "image/jpeg", "data": encoded_data2}
        ]

        storage_parts, gemini_msg = llm_service.prepare_messages(user_msg, media)

        # Verify storage_parts
        assert len(storage_parts) == 3
        assert storage_parts[0] == {"text": user_msg}
        assert storage_parts[1]["inline_data"]["mime_type"] == "image/png"
        assert storage_parts[2]["inline_data"]["mime_type"] == "image/jpeg"

        # Verify gemini_msg
        assert len(gemini_msg) == 3
        assert gemini_msg[0].text == user_msg
        assert gemini_msg[1].inline_data.data == dummy_data1
        assert gemini_msg[2].inline_data.data == dummy_data2

    def test_empty_input(self):
        """Test with empty inputs."""
        user_msg = ""
        media = []

        storage_parts, gemini_msg = llm_service.prepare_messages(user_msg, media)

        assert len(storage_parts) == 0
        assert len(gemini_msg) == 0
