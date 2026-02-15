"""Shared fixtures for tests."""

import sys
import os
import pytest
from fastapi.testclient import TestClient

# Ensure app is importable
sys.path.append(os.getcwd())

# Import app directly from main
# pylint: disable=wrong-import-position
from app.main import app
from app.services.database import DatabaseManager


@pytest.fixture(name="client")
def fixture_client():
    """Fixture to provide a TestClient instance."""
    # Use context manager to trigger lifespan events (startup/shutdown)
    # This ensures DatabaseManager.init_db() is called.
    with TestClient(app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure we start with a clean DB state or mocked DB for each test."""
    # This might be tricky if we want to use a real file DB for tests.
    # Ideally, we should patch DATABASE_URL to a temp file for ALL tests.
    # But since I can't easily patch module-level constant globally for all tests without some hacking...
    # I'll let it use app.db? No, that messes up local dev environment.
    # I should patch DATABASE_URL in conftest.
    pass


@pytest.fixture(autouse=True)
def mock_db_path(tmp_path):
    """
    Patch DATABASE_URL to use a temporary file for all tests.
    This ensures tests don't overwrite local app.db.
    """
    db_path = tmp_path / "test_app.db"

    # We need to patch where it is used.
    # It is used in app.services.database.DatabaseManager.__new__ (it reads DATABASE_URL global)
    # And app.services.database.DATABASE_URL global.

    from unittest.mock import patch

    # Reset singleton
    DatabaseManager._instance = None

    with patch("app.services.database.DATABASE_URL", str(db_path)):
        # We also need to re-init the singleton if it was already created?
        # Since we reset _instance, next instantiation will use new path if we patch correctly.
        # But DatabaseManager reads DATABASE_URL at module level?
        # No, my implementation reads it in __new__?
        # Let's check my implementation.
        yield

    DatabaseManager._instance = None
