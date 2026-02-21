"""
Tests for prompt_router service.
"""

import json
from unittest.mock import patch, mock_open
from app.services.prompt_router import load_active_persona, PERSONA_FILE


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
