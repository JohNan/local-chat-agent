"""
Tests for the Jules router.
"""

from unittest.mock import AsyncMock
import pytest


@pytest.fixture(name="mock_jules_api")
def fixture_mock_jules_api(mocker):
    """Fixture to mock jules_api in the router."""
    mock = mocker.patch("app.routers.jules.jules_api")
    mock.get_session_status = AsyncMock()
    return mock


def test_get_jules_session_status_success(client, mock_jules_api):
    """Test successful status retrieval of a Jules session."""
    session_name = "sessions/test-session"
    mock_jules_api.get_session_status.return_value = {
        "name": session_name,
        "state": "ACTIVE",
    }

    response = client.get(f"/api/jules_session/{session_name}")

    assert response.status_code == 200
    assert response.json() == {"name": session_name, "state": "ACTIVE"}
    mock_jules_api.get_session_status.assert_called_once_with(session_name)


def test_get_jules_session_status_error(client, mock_jules_api):
    """Test error handling when status retrieval fails."""
    session_name = "sessions/error-session"
    mock_jules_api.get_session_status.side_effect = Exception("API failure")

    response = client.get(f"/api/jules_session/{session_name}")

    assert response.status_code == 500
    assert response.json() == {"success": False, "error": "API failure"}
    mock_jules_api.get_session_status.assert_called_once_with(session_name)
