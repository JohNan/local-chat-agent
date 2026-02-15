"""
Tests for RAG triggering on git pull.
"""

import time
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app


def test_rag_git_pull_trigger():
    """Verifies that RAG indexing is triggered after a successful git pull."""

    with patch("app.services.git_ops.perform_git_pull") as mock_git_pull, patch(
        "app.services.rag_manager.index_codebase_task"
    ) as mock_rag_task:

        # Mock successful git pull
        mock_git_pull.return_value = {"success": True, "output": "Updated"}

        with TestClient(app) as client:
            # Wait for startup task to likely complete
            time.sleep(0.5)
            # Reset mock to ignore startup call
            mock_rag_task.reset_mock()

            response = client.post("/api/git_pull")
            assert response.status_code == 200
            assert response.json()["success"] is True

            # Wait briefly for the background task to start
            time.sleep(0.1)

            assert (
                mock_rag_task.called
            ), "RAG indexing task should be called after successful git pull"


def test_rag_git_pull_fail_no_trigger():
    """Verifies that RAG indexing is NOT triggered after a failed git pull."""

    with patch("app.services.git_ops.perform_git_pull") as mock_git_pull, patch(
        "app.services.rag_manager.index_codebase_task"
    ) as mock_rag_task:

        # Mock failed git pull
        mock_git_pull.return_value = {"success": False, "output": "Failed"}

        with TestClient(app) as client:
            # Wait for startup task to likely complete
            time.sleep(0.5)
            # Reset mock to ignore startup call
            mock_rag_task.reset_mock()

            response = client.post("/api/git_pull")
            assert response.status_code == 200
            assert response.json()["success"] is False

            # Wait briefly just in case
            time.sleep(0.1)

            assert (
                not mock_rag_task.called
            ), "RAG indexing task should NOT be called after failed git pull"
