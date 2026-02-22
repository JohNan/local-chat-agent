"""
Test for LSP boot logic.
"""

import unittest
from unittest.mock import patch
from app.services.lsp_manager import LSPManager


class TestLSPBoot(unittest.TestCase):
    """Tests for LSP boot logic."""

    def setUp(self):
        # Reset singleton
        # pylint: disable=protected-access
        LSPManager._instance = None
        LSPManager._servers = {}

    @patch("app.services.lsp_manager.LSPRegistry")
    @patch("app.services.lsp_manager.os.walk")
    @patch("app.services.lsp_manager.LSPManager.start_server")
    def test_start_supported_servers(
        self, mock_start_server, mock_walk, mock_registry_cls
    ):
        """Tests that start_supported_servers correctly identifies and starts servers."""
        import os

        # Setup Registry Mock
        mock_registry = mock_registry_cls.return_value
        # pylint: disable=protected-access
        mock_registry._config = {
            "python": {"extensions": [".py"]},
            "typescript": {"extensions": [".ts", ".tsx"]},
            "kotlin": {"extensions": [".kt"]},
        }

        # Setup os.walk Mock
        # Simulate finding a python file and a typescript file, but no kotlin file
        # Python: 2 files -> Should start
        # TypeScript: 1 file -> Should NOT start
        # Kotlin: 0 files -> Should NOT start
        mock_walk.return_value = [
            (".", ["src"], ["main.py", "utils.py", "README.md"]),
            ("./src", [], ["app.ts"]),
        ]

        manager = LSPManager()
        manager.start_supported_servers(".")

        expected_path = os.path.abspath(".")

        # Check calls
        # Should attempt to start python server (because of main.py and utils.py)
        mock_start_server.assert_any_call("python", expected_path)

        # Should NOT attempt to start typescript server (because only 1 file)
        calls = [args[0] for args, _ in mock_start_server.call_args_list]
        self.assertNotIn("typescript", calls)

        # Should NOT attempt to start kotlin server
        self.assertNotIn("kotlin", calls)

        # Ensure we only called start_server once
        self.assertEqual(mock_start_server.call_count, 1)


if __name__ == "__main__":
    unittest.main()
