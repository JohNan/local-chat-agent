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
        if "DATABASE_URL" in os.environ:
            del os.environ["DATABASE_URL"]

    def test_get_storage_path_priority_1_env_var(self):
        with patch.dict(os.environ, {"MY_VAR": "/custom/path.json"}):
            from app.services import storage

            importlib.reload(storage)
            path = storage.get_storage_path("MY_VAR", "default.json")
            self.assertEqual(path, "/custom/path.json")

    def test_get_storage_path_priority_2_config_dir(self):
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

        with patch("os.path.exists", side_effect=side_effect_exists), patch(
            "os.path.isdir", side_effect=side_effect_isdir
        ), patch("os.access", side_effect=side_effect_access):
            from app.services import storage

            importlib.reload(storage)
            path = storage.get_storage_path("MY_VAR", "default.json")
            self.assertEqual(path, "/config/default.json")

    def test_get_storage_path_fallback(self):
        # Ensure /config does not appear to exist
        original_exists = os.path.exists

        def side_effect_exists(path):
            if path == "/config":
                return False
            return original_exists(path)

        with patch("os.path.exists", side_effect=side_effect_exists):
            from app.services import storage

            importlib.reload(storage)
            path = storage.get_storage_path("MY_VAR", "default.json")
            self.assertEqual(path, "default.json")

    def test_database_integration(self):
        """Verify database uses the configured path."""
        with patch.dict(os.environ, {"DATABASE_URL": "/env/app.db"}):
            from app.services import database

            importlib.reload(database)
            self.assertEqual(database.DATABASE_URL, "/env/app.db")


if __name__ == "__main__":
    unittest.main()
