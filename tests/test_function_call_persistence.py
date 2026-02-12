"""
Tests for function call persistence sanitization.
"""

import unittest
import os
import json
from app.services import chat_manager


class TestChatManagerSanitization(unittest.TestCase):
    """Test suite for sanitizing chat history with incomplete function calls."""

    def setUp(self):
        """Set up the test environment."""
        self.original_chat_history_file = chat_manager.CHAT_HISTORY_FILE
        chat_manager.CHAT_HISTORY_FILE = "test_chat_history_sanitization.json"

    def tearDown(self):
        """Clean up the test environment."""
        if os.path.exists(chat_manager.CHAT_HISTORY_FILE):
            os.remove(chat_manager.CHAT_HISTORY_FILE)
        chat_manager.CHAT_HISTORY_FILE = self.original_chat_history_file

    def test_sanitize_dangling_function_call_snake_case(self):
        """Test sanitizing dangling function calls in snake_case."""
        history = [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"function_call": {"name": "test"}}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")

    def test_sanitize_dangling_function_call_camel_case(self):
        """Test sanitizing dangling function calls in camelCase."""
        history = [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "test"}}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")

    def test_sanitize_orphaned_function_response_snake_case(self):
        """Test sanitizing orphaned function responses in snake_case."""
        history = [
            {"role": "function", "parts": [{"function_response": {"name": "test"}}]},
            {"role": "user", "parts": [{"text": "Hello"}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")

    def test_sanitize_orphaned_function_response_camel_case(self):
        """Test sanitizing orphaned function responses in camelCase."""
        history = [
            {"role": "function", "parts": [{"functionResponse": {"name": "test"}}]},
            {"role": "user", "parts": [{"text": "Hello"}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
