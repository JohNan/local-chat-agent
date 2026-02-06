"""
Tests for app.services.jules_api
"""

import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import aiohttp

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import jules_api  # pylint: disable=wrong-import-position


@pytest.mark.asyncio
async def test_deploy_to_jules_success():
    """Test successful deployment."""
    prompt = "Test prompt"
    repo_info = {"source_id": "src-123", "branch": "test-branch"}

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"success": True}

    # Mock the context manager returned by client.post
    mock_post_ctx = AsyncMock()
    mock_post_ctx.__aenter__.return_value = mock_response

    mock_client = MagicMock()
    mock_client.post.return_value = mock_post_ctx

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch(
            "aiohttp.ClientSession", return_value=MagicMock()
        ) as mock_client_cls:
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
            assert kwargs["json"]["automationMode"] == "AUTO_CREATE_PR"


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
    mock_response = AsyncMock()
    mock_response.status = 500
    mock_response.text.return_value = "Internal Error"

    mock_post_ctx = AsyncMock()
    mock_post_ctx.__aenter__.return_value = mock_response

    mock_client = MagicMock()
    mock_client.post.return_value = mock_post_ctx

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch(
            "aiohttp.ClientSession", return_value=MagicMock()
        ) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            with pytest.raises(RuntimeError, match="Jules API Error: 500"):
                await jules_api.deploy_to_jules("prompt", {"source_id": "123"})


@pytest.mark.asyncio
async def test_deploy_to_jules_request_exception():
    """Test request exception."""
    mock_client = MagicMock()
    mock_client.post.side_effect = aiohttp.ClientError("Connection failed")

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch(
            "aiohttp.ClientSession", return_value=MagicMock()
        ) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            with pytest.raises(aiohttp.ClientError):
                await jules_api.deploy_to_jules("prompt", {"source_id": "123"})


@pytest.mark.asyncio
async def test_get_session_status_success():
    """Test successful status retrieval."""
    session_name = "sessions/123"

    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json.return_value = {"state": "SUCCEEDED"}

    mock_get_ctx = AsyncMock()
    mock_get_ctx.__aenter__.return_value = mock_response

    mock_client = MagicMock()
    mock_client.get.return_value = mock_get_ctx

    with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
        with patch(
            "aiohttp.ClientSession", return_value=MagicMock()
        ) as mock_client_cls:
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            result = await jules_api.get_session_status(session_name)
            assert result == {"state": "SUCCEEDED"}

            mock_client.get.assert_called_once()
