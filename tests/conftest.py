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
def clean_db(tmp_path):
    """
    Ensure we start with a clean DB state for each test.
    This replaces the need for patching DATABASE_URL globally.
    """
    db_path = tmp_path / "test_app.db"

    # Reset singleton to ensure a fresh start
    DatabaseManager.reset_instance()

    # Initialize with temp path
    # This will set the singleton instance with the temp path
    db = DatabaseManager(db_url=str(db_path))
    db.init_db()

    yield db

    # Reset singleton after test so subsequent tests don't use this instance
    DatabaseManager.reset_instance()


@pytest.fixture(autouse=True)
def mock_lifespan_components(mocker):
    """Mock lifespan components to avoid timeouts."""
    mocker.patch("app.main.get_mcp_servers", return_value={})
    mocker.patch("app.main.rag_manager.index_codebase_task")
    mocker.patch("app.main.LSPManager")
