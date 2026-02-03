"""
Tests for the chat manager service.
"""

# pylint: disable=wrong-import-position

import json
import os
import sys

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import chat_manager


def test_load_history_normal(mocker):
    """
    Test loading a normal history file without any issues.
    """
    normal_history = [
        {"role": "user", "parts": [{"text": "Hello"}]},
        {"role": "model", "parts": [{"text": "Hi there"}]},
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data=json.dumps(normal_history))
    )

    history = chat_manager.load_chat_history()
    assert len(history) == 2

    # Check content matches and IDs are present
    assert history[0]["role"] == normal_history[0]["role"]
    assert history[0]["parts"] == normal_history[0]["parts"]
    assert "id" in history[0]

    assert history[1]["role"] == normal_history[1]["role"]
    assert history[1]["parts"] == normal_history[1]["parts"]
    assert "id" in history[1]


def test_load_history_dangling_function_call(mocker):
    """
    Test that a history ending with a function call is sanitized.
    """
    dangling_history = [
        {"role": "user", "parts": [{"text": "Do something"}]},
        {"role": "model", "parts": [{"function_call": {"name": "foo", "args": {}}}]},
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data=json.dumps(dangling_history))
    )

    # Mock logger to verify warning
    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    # Should remove the last message
    assert len(history) == 1
    assert history[0]["role"] == "user"
    mock_logger.warning.assert_called_with(
        "Detected incomplete function call in history. "
        "Removed last message to prevent API error."
    )


def test_load_history_orphaned_function_response(mocker):
    """
    Test that a history starting with a function response is sanitized.
    """
    orphaned_history = [
        {
            "role": "function",
            "parts": [{"function_response": {"name": "foo", "response": {}}}],
        },
        {"role": "model", "parts": [{"text": "Ok"}]},
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data=json.dumps(orphaned_history))
    )

    # Mock logger
    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    assert len(history) == 1
    assert history[0]["role"] == "model"
    # Verify warning if applicable
    mock_logger.warning.assert_called()


def test_load_history_complex_parts(mocker):
    """
    Test sanitization when function calls are embedded in complex parts.
    """
    # Test with multiple parts where one might be function call
    dangling_history = [
        {"role": "user", "parts": [{"text": "check this"}]},
        {
            "role": "model",
            "parts": [
                {"text": "thinking..."},
                {"function_call": {"name": "foo", "args": {}}},
            ],
        },
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch(
        "builtins.open", mocker.mock_open(read_data=json.dumps(dangling_history))
    )

    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    assert len(history) == 1
    assert history[0]["role"] == "user"
    mock_logger.warning.assert_called()
