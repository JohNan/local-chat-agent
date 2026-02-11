import unittest
import shutil
import os
import json
from app.services import chat_manager


class TestChatManagerSanitization(unittest.TestCase):
    def setUp(self):
        self.original_chat_history_file = chat_manager.CHAT_HISTORY_FILE
        chat_manager.CHAT_HISTORY_FILE = "test_chat_history_sanitization.json"

    def tearDown(self):
        if os.path.exists(chat_manager.CHAT_HISTORY_FILE):
            os.remove(chat_manager.CHAT_HISTORY_FILE)
        chat_manager.CHAT_HISTORY_FILE = self.original_chat_history_file

    def test_sanitize_dangling_function_call_snake_case(self):
        history = [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"function_call": {"name": "test"}}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")

    def test_sanitize_dangling_function_call_camel_case(self):
        history = [
            {"role": "user", "parts": [{"text": "Hello"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "test"}}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")

    def test_sanitize_orphaned_function_response_snake_case(self):
        history = [
            {"role": "function", "parts": [{"function_response": {"name": "test"}}]},
            {"role": "user", "parts": [{"text": "Hello"}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")

    def test_sanitize_orphaned_function_response_camel_case(self):
        history = [
            {"role": "function", "parts": [{"functionResponse": {"name": "test"}}]},
            {"role": "user", "parts": [{"text": "Hello"}]},
        ]
        with open(chat_manager.CHAT_HISTORY_FILE, "w") as f:
            json.dump(history, f)

        loaded = chat_manager.load_chat_history()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["role"], "user")


if __name__ == "__main__":
    unittest.main()
