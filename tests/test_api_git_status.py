"""
Tests for the /api/git_status endpoint.
"""


def test_api_git_status_empty(client, mocker):
    """Test /api/git_status when there are no changes."""
    mock_get_status = mocker.patch("app.routers.system.git_ops.get_git_status")
    mock_get_status.return_value = []

    mocker.patch("app.routers.system.git_ops.get_current_branch", return_value="main")
    mocker.patch("app.routers.system.git_ops.get_local_diff", return_value="")

    response = client.get("/api/git_status")
    data = response.json()

    assert response.status_code == 200
    assert data == {
        "status": [],
        "branch": "main",
        "suggested_commit_message": "chore: update files",
    }
    mock_get_status.assert_called_once()


def test_api_git_status_with_changes(client, mocker):
    """Test /api/git_status when there are changed files."""
    mock_get_status = mocker.patch("app.routers.system.git_ops.get_git_status")
    changes = [" M app/main.py", "?? tests/test_api_git_status.py"]
    mock_get_status.return_value = changes

    mocker.patch(
        "app.routers.system.git_ops.get_current_branch", return_value="feature-branch"
    )
    mocker.patch(
        "app.routers.system.git_ops.get_local_diff", return_value="some diff content"
    )

    # Mock the LLM client behavior
    mock_client = mocker.patch("app.routers.system.CLIENT")
    mock_response = mocker.MagicMock()
    mock_response.text = "feat: update git status test"
    mock_client.models.generate_content.return_value = mock_response

    response = client.get("/api/git_status")
    data = response.json()

    assert response.status_code == 200
    assert data == {
        "status": changes,
        "branch": "feature-branch",
        "suggested_commit_message": "feat: update git status test",
    }
    mock_get_status.assert_called_once()
