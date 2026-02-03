"""
Tests for app.services.jules_api
"""

import os
import sys
import asyncio
from unittest.mock import MagicMock, patch
import pytest
import requests

# Ensure we can import app from the root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services import jules_api  # pylint: disable=wrong-import-position


def test_deploy_to_jules_success():
    """Test successful deployment."""

    async def run_test():
        prompt = "Test prompt"
        repo_info = {"source_id": "src-123", "branch": "test-branch"}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response) as mock_post:
                result = await jules_api.deploy_to_jules(prompt, repo_info)

                assert result == {"success": True}

                mock_post.assert_called_once()
                _, kwargs = mock_post.call_args
                assert kwargs["json"]["prompt"] == prompt
                assert kwargs["json"]["sourceContext"]["source"] == "src-123"
                assert (
                    kwargs["json"]["sourceContext"]["githubRepoContext"][
                        "startingBranch"
                    ]
                    == "test-branch"
                )

    asyncio.run(run_test())


def test_deploy_to_jules_missing_api_key():
    """Test missing API key."""

    async def run_test():
        # Ensure no keys are present
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="not set"):
                await jules_api.deploy_to_jules("prompt", {"source_id": "123"})

    asyncio.run(run_test())


def test_deploy_to_jules_missing_source_id():
    """Test missing source ID."""

    async def run_test():
        with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
            with pytest.raises(ValueError, match="Source ID"):
                await jules_api.deploy_to_jules("prompt", {})

    asyncio.run(run_test())


def test_deploy_to_jules_api_error():
    """Test API error."""

    async def run_test():
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Error"

        with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response):
                with pytest.raises(RuntimeError, match="Jules API Error: 500"):
                    await jules_api.deploy_to_jules("prompt", {"source_id": "123"})

    asyncio.run(run_test())


def test_deploy_to_jules_request_exception():
    """Test request exception."""

    async def run_test():
        with patch.dict(os.environ, {"JULES_API_KEY": "test-key"}):
            with patch(
                "requests.post",
                side_effect=requests.RequestException("Connection failed"),
            ):
                with pytest.raises(requests.RequestException):
                    await jules_api.deploy_to_jules("prompt", {"source_id": "123"})

    asyncio.run(run_test())
