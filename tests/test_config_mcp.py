"""
Tests for get_mcp_servers in app/config.py
"""

import json
from unittest.mock import mock_open
from app.config import get_mcp_servers


def test_get_mcp_servers_file_not_exists(mocker):
    """Test that it returns an empty dict if the file does not exist."""
    mocker.patch("os.path.exists", return_value=False)
    assert get_mcp_servers() == {}


def test_get_mcp_servers_invalid_json(mocker):
    """Test that it returns an empty dict and logs an error if JSON is invalid."""
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data="invalid json"))

    mock_logger = mocker.patch("app.config.logger")

    result = get_mcp_servers()

    assert result == {}
    mock_logger.error.assert_called()
    # Check if the specific error message is logged
    args, _ = mock_logger.error.call_args
    assert "Failed to parse mcp_servers.json" in args[0]


def test_get_mcp_servers_generic_exception(mocker):
    """Test that it returns an empty dict and logs an error on generic Exception."""
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", side_effect=Exception("Generic error"))

    mock_logger = mocker.patch("app.config.logger")

    result = get_mcp_servers()

    assert result == {}
    mock_logger.error.assert_called()
    args, _ = mock_logger.error.call_args
    assert "Error reading mcp_servers.json" in args[0]


def test_get_mcp_servers_success(mocker):
    """Test that it returns the parsed JSON on success."""
    mcp_data = {"mcpServers": {"test-server": {"command": "test"}}}
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mock_open(read_data=json.dumps(mcp_data)))

    assert get_mcp_servers() == mcp_data
