import os
import unittest
from unittest.mock import patch, MagicMock
import importlib
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

class TestStorageConfig(unittest.TestCase):
    def setUp(self):
        # Clean up env vars before each test
        if "JULES_TASKS_FILE" in os.environ:
            del os.environ["JULES_TASKS_FILE"]
        if "CHAT_HISTORY_FILE" in os.environ:
            del os.environ["CHAT_HISTORY_FILE"]

    def test_tasks_file_priority_1_env_var(self):
        with patch.dict(os.environ, {"JULES_TASKS_FILE": "/custom/tasks.json"}):
            from app.services import task_manager
            importlib.reload(task_manager)
            self.assertEqual(task_manager.TASKS_FILE, "/custom/tasks.json")

    def test_tasks_file_priority_2_config_dir(self):
        # We need to ensure os.path.exists returns True for /config only
        original_exists = os.path.exists
        original_isdir = os.path.isdir
        original_access = os.access

        def side_effect_exists(path):
            if path == "/config":
                return True
            return original_exists(path)

        def side_effect_isdir(path):
            if path == "/config":
                return True
            return original_isdir(path)

        def side_effect_access(path, mode):
            if path == "/config" and mode == os.W_OK:
                return True
            return original_access(path, mode)

        with patch("os.path.exists", side_effect=side_effect_exists), \
             patch("os.path.isdir", side_effect=side_effect_isdir), \
             patch("os.access", side_effect=side_effect_access):

            from app.services import task_manager
            importlib.reload(task_manager)
            self.assertEqual(task_manager.TASKS_FILE, "/config/tasks.json")

    def test_tasks_file_fallback(self):
        # Ensure /config does not appear to exist
        original_exists = os.path.exists

        def side_effect_exists(path):
            if path == "/config":
                return False
            return original_exists(path)

        with patch("os.path.exists", side_effect=side_effect_exists):
            from app.services import task_manager
            importlib.reload(task_manager)
            self.assertEqual(task_manager.TASKS_FILE, "tasks.json")

    def test_chat_history_file_priority_1_env_var(self):
        with patch.dict(os.environ, {"CHAT_HISTORY_FILE": "/custom/chat.json"}):
            from app.services import chat_manager
            importlib.reload(chat_manager)
            self.assertEqual(chat_manager.CHAT_HISTORY_FILE, "/custom/chat.json")

    def test_chat_history_file_priority_2_config_dir(self):
        original_exists = os.path.exists
        original_isdir = os.path.isdir
        original_access = os.access

        def side_effect_exists(path):
            if path == "/config":
                return True
            return original_exists(path)

        def side_effect_isdir(path):
            if path == "/config":
                return True
            return original_isdir(path)

        def side_effect_access(path, mode):
            if path == "/config" and mode == os.W_OK:
                return True
            return original_access(path, mode)

        with patch("os.path.exists", side_effect=side_effect_exists), \
             patch("os.path.isdir", side_effect=side_effect_isdir), \
             patch("os.access", side_effect=side_effect_access):

            from app.services import chat_manager
            importlib.reload(chat_manager)
            self.assertEqual(chat_manager.CHAT_HISTORY_FILE, "/config/chat_history.json")

    def test_chat_history_file_fallback(self):
        original_exists = os.path.exists

        def side_effect_exists(path):
            if path == "/config":
                return False
            return original_exists(path)

        with patch("os.path.exists", side_effect=side_effect_exists):
            from app.services import chat_manager
            importlib.reload(chat_manager)
            self.assertEqual(chat_manager.CHAT_HISTORY_FILE, "chat_history.json")

if __name__ == '__main__':
    unittest.main()
