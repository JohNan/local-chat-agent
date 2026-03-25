"""
Tests for the /api/git_status endpoint.
"""

def test_api_git_status_empty(client, mocker):
    """Test /api/git_status when there are no changes."""
    mock_get_status = mocker.patch("app.routers.system.git_ops.get_git_status")
    mock_get_status.return_value = []

    response = client.get("/api/git_status")
    data = response.json()

    assert response.status_code == 200
    assert data == {"status": []}
    mock_get_status.assert_called_once()

def test_api_git_status_with_changes(client, mocker):
    """Test /api/git_status when there are changed files."""
    mock_get_status = mocker.patch("app.routers.system.git_ops.get_git_status")
    changes = [" M app/main.py", "?? tests/test_api_git_status.py"]
    mock_get_status.return_value = changes

    response = client.get("/api/git_status")
    data = response.json()

    assert response.status_code == 200
    assert data == {"status": changes}
    mock_get_status.assert_called_once()
