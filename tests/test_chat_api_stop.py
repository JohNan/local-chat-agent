"""
Tests for the /api/stop endpoint in the chat router.
"""

from unittest.mock import patch


def test_api_stop_no_active_task(client):
    """Test /api/stop when no task is running."""
    with patch("app.routers.chat.agent_engine.cancel_current_task", return_value=False):
        response = client.post("/api/stop")

    assert response.status_code == 200
    assert response.json() == {"status": "no_active_task"}


def test_api_stop_success(client):
    """Test /api/stop when a task is successfully stopped."""
    with patch("app.routers.chat.agent_engine.cancel_current_task", return_value=True):
        response = client.post("/api/stop")

    assert response.status_code == 200
    assert response.json() == {"status": "stopped"}
