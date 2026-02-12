"""
Tests for context reset logic.
"""

import sys
import os

# Add app to path
sys.path.append(os.getcwd())

# pylint: disable=wrong-import-position, protected-access
from app.main import (
    _format_history,
)


def test_format_history_no_marker():
    """Test formatting history without reset marker."""
    history = [
        {"role": "user", "parts": [{"text": "Hello"}]},
        {"role": "model", "parts": [{"text": "Hi"}]},
        {"role": "user", "parts": [{"text": "How are you?"}]},
    ]
    # Should exclude last user message
    formatted = _format_history(history)
    assert len(formatted) == 2
    assert formatted[0]["role"] == "user"
    assert formatted[1]["role"] == "model"


def test_format_history_with_marker():
    """Test formatting history with reset marker."""
    history = [
        {"role": "user", "parts": [{"text": "Old 1"}]},
        {"role": "model", "parts": [{"text": "Old 2"}]},
        {"role": "system", "parts": [{"text": "--- Context Reset ---"}]},
        {"role": "user", "parts": [{"text": "New 1"}]},
        {"role": "model", "parts": [{"text": "New 2"}]},
        {"role": "user", "parts": [{"text": "New 3"}]},
    ]
    # Should slice after marker, then exclude last message
    # Slice: [New 1, New 2, New 3]
    # Exclude last: [New 1, New 2]
    formatted = _format_history(history)
    assert len(formatted) == 2
    assert formatted[0]["parts"][0].text == "New 1"
    assert formatted[1]["parts"][0].text == "New 2"


def test_format_history_marker_at_end():
    """Test formatting history with marker at end."""
    history = [
        {"role": "user", "parts": [{"text": "Old 1"}]},
        {"role": "system", "parts": [{"text": "--- Context Reset ---"}]},
    ]
    # Slice: []
    # Exclude last: []
    formatted = _format_history(history)
    assert len(formatted) == 0


def test_format_history_marker_then_one_msg():
    """Test formatting history with marker then one message."""
    history = [
        {"role": "system", "parts": [{"text": "--- Context Reset ---"}]},
        {"role": "user", "parts": [{"text": "New 1"}]},
    ]
    # Slice: [New 1]
    # Exclude last: []
    formatted = _format_history(history)
    assert len(formatted) == 0


def test_format_history_multiple_markers():
    """Test formatting history with multiple markers."""
    history = [
        {"role": "user", "parts": [{"text": "Old 1"}]},
        {"role": "system", "parts": [{"text": "Reset 1"}]},
        {"role": "user", "parts": [{"text": "Mid 1"}]},
        {"role": "system", "parts": [{"text": "Reset 2"}]},
        {"role": "user", "parts": [{"text": "New 1"}]},
        {"role": "model", "parts": [{"text": "New 2"}]},
        {"role": "user", "parts": [{"text": "New 3"}]},
    ]
    # Slice: [New 1, New 2, New 3]
    # Exclude last: [New 1, New 2]
    formatted = _format_history(history)
    assert len(formatted) == 2
    assert formatted[0]["parts"][0].text == "New 1"
