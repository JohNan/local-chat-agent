"""
Tests for LSP manager and related Git operations.
"""

import json
import unittest.mock
from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.services.lsp_registry import LSPRegistry
from app.services.lsp_manager import LSPManager
from app.services import git_ops

# Mock config content
MOCK_CATALOG = {
    "python": {"bin": "pylsp", "args": [], "extensions": [".py"]},
    "testlang": {"bin": "test-ls", "args": [], "extensions": [".test"]},
}


@pytest.fixture
def mock_registry():
    """Fixture to provide a mock LSP registry."""
    # Reset singleton
    LSPRegistry._instance = None  # pylint: disable=protected-access
    LSPRegistry._config = {}  # pylint: disable=protected-access
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CATALOG))), patch(
        "os.path.exists", return_value=True
    ), patch("shutil.which", return_value="/usr/bin/test-ls"):
        registry = LSPRegistry()
        yield registry
    LSPRegistry._instance = None  # pylint: disable=protected-access
    LSPRegistry._config = {}  # pylint: disable=protected-access


def test_registry_loading(mock_registry):
    """Test that the registry loads configurations correctly."""
    config = mock_registry.get_config_by_extension(".py")
    assert config is not None
    assert config["bin"] == "pylsp"


def test_registry_missing_binary():
    """Test that the registry handles missing binaries correctly."""
    LSPRegistry._instance = None  # pylint: disable=protected-access
    LSPRegistry._config = {}  # pylint: disable=protected-access
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CATALOG))), patch(
        "os.path.exists", return_value=True
    ), patch(
        "shutil.which", side_effect=lambda x: None
    ):  # Binary not found
        registry = LSPRegistry()
        config = registry.get_config_by_extension(".py")
        assert config is None
    LSPRegistry._instance = None  # pylint: disable=protected-access
    LSPRegistry._config = {}  # pylint: disable=protected-access


@pytest.fixture
def mock_lsp_manager():
    """Fixture to provide a mock LSP manager."""
    LSPManager._instance = None  # pylint: disable=protected-access
    LSPManager._servers = {}  # pylint: disable=protected-access
    return LSPManager()


@pytest.mark.asyncio
@patch("subprocess.Popen")
@patch("app.services.lsp_manager.LSPRegistry")
async def test_lsp_manager_start_server(
    mock_registry_cls, mock_popen, mock_lsp_manager
):
    """Test starting an LSP server via LSPManager."""
    # Setup Registry Mock
    registry_instance = MagicMock()
    registry_instance._config = {  # pylint: disable=protected-access
        "python": {"bin": "pylsp", "args": []}
    }
    # We need to make sure get_config_by_extension works or just relying on _config access
    mock_registry_cls.return_value = registry_instance

    # Setup Popen Mock
    process_mock = MagicMock()
    process_mock.poll.return_value = None
    mock_popen.return_value = process_mock

    # We patch LSPServer to avoid threading issues in tests
    with patch("app.services.lsp_manager.LSPServer") as mock_lspserver_cls:
        server_instance = MagicMock()
        server_instance.process = process_mock
        server_instance.send_request.return_value = {
            "result": {"capabilities": {}}
        }  # Success response
        mock_lspserver_cls.return_value = server_instance

        # We patch threading.Thread so the background task runs inline synchronously
        with patch("threading.Thread") as mock_thread:

            # When Thread() is called, create a mock thread that just executes its target
            # immediately when start() is called
            class FakeThread:  # pylint: disable=too-few-public-methods
                """Fake thread class to execute target immediately."""

                def __init__(self, target, args, daemon):
                    self.target = target
                    self.args = args

                def start(self):
                    """Execute the target with provided arguments."""
                    self.target(*self.args)

            mock_thread.side_effect = FakeThread

            server = await mock_lsp_manager.start_server("python", "/root")

            assert server is not None
            assert mock_popen.called
            assert server_instance.send_request.called  # initialize called

            # Verify initialization timeout is 300.0 (the new default from config)
            # server_instance.send_request.call_args is a tuple (args, kwargs)
            args, kwargs = server_instance.send_request.call_args
            assert args[0] == "initialize"
            assert kwargs["timeout"] == 300.0


@pytest.mark.asyncio
@patch("app.services.git_ops.LSPManager")
@patch("app.services.git_ops.read_file")
async def test_git_ops_get_definition(mock_read_file, mock_lsp_manager_cls):
    """Test getting definition via Git operations."""
    manager_instance = MagicMock()
    mock_lsp_manager_cls.return_value = manager_instance

    mock_result = {
        "result": [
            {
                "uri": f"file://{git_ops.CODEBASE_ROOT}/test.py",
                "range": {
                    "start": {"line": 10, "character": 5},
                    "end": {"line": 10, "character": 15},
                },
            }
        ]
    }

    async def mock_get_definition(*_args, **_kwargs):
        """Mocked get_definition method."""
        return mock_result

    manager_instance.get_definition.side_effect = mock_get_definition
    mock_read_file.return_value = "def my_func():\n    pass"

    # We also need to mock os.path.relpath behavior since CODEBASE_ROOT is used
    # But git_ops sets CODEBASE_ROOT from env or default.
    # Assuming test env has reasonable path handling.

    with patch("os.path.relpath", return_value="test.py"):
        result = await git_ops.get_definition("main.py", 1, 1)

    assert result["file"] == "test.py"
    assert result["line"] == 11  # 10 + 1
    assert result["content"] == "def my_func():\n    pass"
