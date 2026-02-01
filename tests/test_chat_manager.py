import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import chat_manager

def test_load_history_normal(mocker):
    normal_history = [
        {"role": "user", "parts": [{"text": "Hello"}]},
        {"role": "model", "parts": [{"text": "Hi there"}]}
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(normal_history)))

    history = chat_manager.load_chat_history()
    assert len(history) == 2
    assert history == normal_history

def test_load_history_dangling_function_call(mocker):
    dangling_history = [
        {"role": "user", "parts": [{"text": "Do something"}]},
        {"role": "model", "parts": [{"function_call": {"name": "foo", "args": {}}}]}
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(dangling_history)))

    # Mock logger to verify warning
    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    # Should remove the last message
    assert len(history) == 1
    assert history[0]["role"] == "user"
    mock_logger.warning.assert_called_with("Detected incomplete function call in history. Removed last message to prevent API error.")

def test_load_history_orphaned_function_response(mocker):
    orphaned_history = [
        {"role": "function", "parts": [{"function_response": {"name": "foo", "response": {}}}]},
        {"role": "model", "parts": [{"text": "Ok"}]}
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(orphaned_history)))

    # Mock logger
    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    # Should remove the first message?
    # The requirement says "ensure that we do not load a history that starts with a function_response"
    # If I remove the first, I have [model_msg].
    # Wait, usually conversation starts with user. If I remove the first one, the next one is model.
    # That might be valid or invalid depending on API.
    # But for this specific requirement, let's assume we just drop the invalid start.

    # If implementation clears it, that's also fine. But removal is likely.
    # Actually, if the first message is function_response, it's definitely garbage.

    assert len(history) == 1
    assert history[0]["role"] == "model"
    # Verify warning if applicable, or maybe info.
    # Requirement: "Log a warning if history was modified"
    mock_logger.warning.assert_called()

def test_load_history_complex_parts(mocker):
    # Test with multiple parts where one might be function call
    dangling_history = [
        {"role": "user", "parts": [{"text": "check this"}]},
        {"role": "model", "parts": [{"text": "thinking..."}, {"function_call": {"name": "foo", "args": {}}}]}
    ]

    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps(dangling_history)))

    mock_logger = mocker.patch("app.services.chat_manager.logger")

    history = chat_manager.load_chat_history()

    assert len(history) == 1
    assert history[0]["role"] == "user"
    mock_logger.warning.assert_called()
