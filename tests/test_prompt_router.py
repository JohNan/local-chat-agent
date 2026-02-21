"""
Tests for prompt_router service.
"""

import json
from unittest.mock import patch, mock_open, MagicMock
from app.services.prompt_router import (
    load_active_persona,
    PERSONA_FILE,
    load_core_instruction,
)


def test_load_active_persona_file_not_found():
    """Test that load_active_persona returns None when the file does not exist."""
    with patch(
        "app.services.prompt_router.os.path.exists", return_value=False
    ) as mock_exists:
        assert load_active_persona() is None
        mock_exists.assert_called_with(PERSONA_FILE)


def test_load_active_persona_success():
    """Test that load_active_persona returns the persona when the file exists and is valid."""
    mock_data = json.dumps({"active_persona": "UI"})
    with patch(
        "app.services.prompt_router.os.path.exists", return_value=True
    ) as mock_exists:
        with patch("builtins.open", mock_open(read_data=mock_data)) as mock_file:
            assert load_active_persona() == "UI"
            mock_exists.assert_called_with(PERSONA_FILE)
            mock_file.assert_called_with(PERSONA_FILE, "r", encoding="utf-8")


def test_load_active_persona_invalid_json():
    """Test that load_active_persona returns None when the file contains invalid JSON."""
    with patch("app.services.prompt_router.os.path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data="invalid json")):
            assert load_active_persona() is None


def test_load_active_persona_io_error():
    """Test that load_active_persona returns None when an IOError occurs."""
    with patch("app.services.prompt_router.os.path.exists", return_value=True):
        with patch("builtins.open", side_effect=IOError("Mocked IO Error")):
            assert load_active_persona() is None


def test_load_core_instruction_priority():
    """Test that /config/system_core.md is prioritized."""
    with patch("app.services.prompt_router.Path") as mock_path:
        # Create mocks for the two paths
        config_path = MagicMock()
        app_path = MagicMock()

        # Configure side_effect to return specific mocks for specific paths
        def side_effect(path_str):
            if str(path_str) == "/config/system_core.md":
                return config_path
            elif str(path_str) == "app/prompts/system_core.md":
                return app_path
            return MagicMock()

        mock_path.side_effect = side_effect

        # Case 1: Config file exists
        config_path.exists.return_value = True
        config_path.read_text.return_value = "Config Content"
        assert load_core_instruction() == "Config Content"

        # Case 2: Config file missing, App file exists
        config_path.exists.return_value = False
        app_path.exists.return_value = True
        app_path.read_text.return_value = "App Content"
        assert load_core_instruction() == "App Content"

        # Case 3: Both missing
        config_path.exists.return_value = False
        app_path.exists.return_value = False
        assert "Error" in load_core_instruction()


def test_load_core_instruction_read_error():
    """Test fallback when reading fails."""
    with patch("app.services.prompt_router.Path") as mock_path:
        config_path = MagicMock()
        app_path = MagicMock()

        def side_effect(path_str):
            if str(path_str) == "/config/system_core.md":
                return config_path
            elif str(path_str) == "app/prompts/system_core.md":
                return app_path
            return MagicMock()

        mock_path.side_effect = side_effect

        # Config exists but read fails
        config_path.exists.return_value = True
        config_path.read_text.side_effect = Exception("Read error")

        app_path.exists.return_value = True
        app_path.read_text.return_value = "App Content"

        assert load_core_instruction() == "App Content"
