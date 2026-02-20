import os
import json
import pytest
import shutil
from unittest.mock import MagicMock, patch, mock_open
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
    # Reset singleton
    LSPRegistry._instance = None
    LSPRegistry._config = {}
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CATALOG))), patch(
        "os.path.exists", return_value=True
    ), patch("shutil.which", return_value="/usr/bin/test-ls"):
        registry = LSPRegistry()
        yield registry
    LSPRegistry._instance = None
    LSPRegistry._config = {}


def test_registry_loading(mock_registry):
    config = mock_registry.get_config_by_extension(".py")
    assert config is not None
    assert config["bin"] == "pylsp"


def test_registry_missing_binary():
    LSPRegistry._instance = None
    LSPRegistry._config = {}
    with patch("builtins.open", mock_open(read_data=json.dumps(MOCK_CATALOG))), patch(
        "os.path.exists", return_value=True
    ), patch(
        "shutil.which", side_effect=lambda x: None
    ):  # Binary not found
        registry = LSPRegistry()
        config = registry.get_config_by_extension(".py")
        assert config is None
    LSPRegistry._instance = None
    LSPRegistry._config = {}


@pytest.fixture
def mock_lsp_manager():
    LSPManager._instance = None
    LSPManager._servers = {}
    return LSPManager()


@patch("subprocess.Popen")
@patch("app.services.lsp_manager.LSPRegistry")
def test_lsp_manager_start_server(MockRegistry, MockPopen, mock_lsp_manager):
    # Setup Registry Mock
    registry_instance = MagicMock()
    registry_instance._config = {"python": {"bin": "pylsp", "args": []}}
    # We need to make sure get_config_by_extension works or just relying on _config access
    MockRegistry.return_value = registry_instance

    # Setup Popen Mock
    process_mock = MagicMock()
    process_mock.poll.return_value = None
    MockPopen.return_value = process_mock

    # We patch LSPServer to avoid threading issues in tests
    with patch("app.services.lsp_manager.LSPServer") as MockLSPServer:
        server_instance = MagicMock()
        server_instance.process = process_mock
        server_instance.send_request.return_value = {
            "result": {"capabilities": {}}
        }  # Success response
        MockLSPServer.return_value = server_instance

        server = mock_lsp_manager.start_server("python", "/root")

        assert server is not None
        assert MockPopen.called
        assert server_instance.send_request.called  # initialize called


@patch("app.services.git_ops.LSPManager")
@patch("app.services.git_ops.read_file")
def test_git_ops_get_definition(mock_read_file, MockLSPManager):
    manager_instance = MagicMock()
    MockLSPManager.return_value = manager_instance

    mock_result = {
        "result": [
            {
                "uri": "file:///codebase/test.py",
                "range": {
                    "start": {"line": 10, "character": 5},
                    "end": {"line": 10, "character": 15},
                },
            }
        ]
    }
    manager_instance.get_definition.return_value = mock_result
    mock_read_file.return_value = "def my_func():\n    pass"

    # We also need to mock os.path.relpath behavior since CODEBASE_ROOT is used
    # But git_ops sets CODEBASE_ROOT from env or default.
    # Assuming test env has reasonable path handling.

    with patch("os.path.relpath", return_value="test.py"):
        result = git_ops.get_definition("main.py", 1, 1)

    assert result["file"] == "test.py"
    assert result["line"] == 11  # 10 + 1
    assert result["content"] == "def my_func():\n    pass"
