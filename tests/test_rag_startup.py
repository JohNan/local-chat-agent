"""
Tests for RAG startup.
"""

# pylint: disable=redefined-outer-name, unused-variable

import time
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from app.main import app


# Ensure we don't actually run the task
@pytest.fixture(autouse=True)
def mock_rag_task():
    """Mock the RAG indexing task."""
    with patch("app.services.rag_manager.index_codebase_task") as mock:
        yield mock


def test_rag_startup_trigger(mock_rag_task):
    """Verifies that RAG indexing is triggered on app startup."""
    with TestClient(app) as client:
        # Just entering the context manager triggers startup
        pass

    # Assert called at least once
    # Since it's run in a separate thread via asyncio.create_task,
    # we might need a small delay or just check if it was scheduled.
    # However, asyncio.to_thread is used, which runs in a separate thread.
    # The TestClient's lifespan management should handle the event loop.

    # Because the task is fired and forgotten in the lifespan,
    # we need to ensure the event loop has a chance to execute the task creation.
    # But checking if the function was called inside to_thread is tricky without waiting.

    # Actually, asyncio.to_thread calls the function in a separate thread.
    # The mock should record the call.

    # Let's add a small sleep to ensure the thread has time to start if needed,
    # although mocks usually record calls immediately if the thread starts.

    # Wait for a brief moment for the thread to be spawned and the function called

    time.sleep(0.1)

    assert mock_rag_task.called, "RAG indexing task should be called on startup"
