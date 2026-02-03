"""
Tests for app.services.jules_api
"""

import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import httpx

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import jules_api  # pylint: disable=wrong-import-position


@pytest.mark.asyncio
async def test_deploy_to_jules_success():
    """Test successful deployment."""
    prompt = "Test prompt"
    repo_info = {"source_id": "src-123", "branch": "test-branch"}

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=MagicMock()) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await jules_api.deploy_to_jules(prompt, repo_info)

            assert result == {"success": True}

            mock_client.post.assert_called_once()
            _, kwargs = mock_client.post.call_args
            assert kwargs["json"]["prompt"] == prompt
            assert kwargs["json"]["sourceContext"]["source"] == "src-123"
            assert (
                kwargs["json"]["sourceContext"]["githubRepoContext"]["startingBranch"]
                == "test-branch"
            )


@pytest.mark.asyncio
async def test_deploy_to_jules_missing_api_key():
    """Test missing API key."""
    # Ensure no keys are present
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="not set"):
            await jules_api.deploy_to_jules("prompt", {"source_id": "123"})


@pytest.mark.asyncio
async def test_deploy_to_jules_missing_source_id():
    """Test missing source ID."""
    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with pytest.raises(ValueError, match="Source ID"):
            await jules_api.deploy_to_jules("prompt", {})


@pytest.mark.asyncio
async def test_deploy_to_jules_api_error():
    """Test API error."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Error"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=MagicMock()) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            with pytest.raises(RuntimeError, match="Jules API Error: 500"):
                await jules_api.deploy_to_jules("prompt", {"source_id": "123"})


@pytest.mark.asyncio
async def test_deploy_to_jules_request_exception():
    """Test request exception."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = httpx.HTTPError("Connection failed")

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch("httpx.AsyncClient", return_value=MagicMock()) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            with pytest.raises(httpx.HTTPError):
                await jules_api.deploy_to_jules("prompt", {"source_id": "123"})
