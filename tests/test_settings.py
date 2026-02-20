"""
Tests for settings functionality.
"""

import os
import sys
import pytest

# Ensure we can import app from the root
sys.path.append(os.getcwd())

from app.services import chat_manager


def test_settings_basic(clean_db):
    """
    Test saving and retrieving settings.
    """
    # Test default
    assert chat_manager.get_setting("non_existent", "default") == "default"

    # Save setting
    chat_manager.save_setting("theme", "dark")

    # Retrieve setting
    assert chat_manager.get_setting("theme") == "dark"

    # Update setting
    chat_manager.save_setting("theme", "light")
    assert chat_manager.get_setting("theme") == "light"


def test_save_setting_upsert(clean_db):
    """
    Test that save_setting correctly upserts values.
    """
    key = "test_key"
    val1 = "val1"
    val2 = "val2"

    chat_manager.save_setting(key, val1)
    assert chat_manager.get_setting(key) == val1

    chat_manager.save_setting(key, val2)
    assert chat_manager.get_setting(key) == val2
