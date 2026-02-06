"""
Service module for interacting with the Jules API.
"""

import logging
import os
import aiohttp

logger = logging.getLogger(__name__)


async def deploy_to_jules(prompt_text, repo_info):
    """
    Deploys a session to Jules API with the provided prompt and repository context.

    Args:
        prompt_text (str): The prompt to send to Jules.
        repo_info (dict): Dictionary containing repository information (source_id, branch).

    Returns:
        dict: The JSON response from the API.

    Raises:
        ValueError: If API keys or source ID are missing.
        RuntimeError: If the Jules API returns an error.
        aiohttp.ClientError: If the HTTP request fails.
    """
    api_key = os.environ.get("JULES_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("JULES_API_KEY or GOOGLE_API_KEY not set")

    source_id = repo_info.get("source_id")
    branch = repo_info.get("branch", "main")

    if not source_id:
        raise ValueError("Could not detect Git repository Source ID.")

    url = "https://jules.googleapis.com/v1alpha/sessions"
    headers = {"X-Goog-Api-Key": api_key, "Content-Type": "application/json"}

    payload = {
        "prompt": prompt_text,
        "sourceContext": {
            "source": source_id,
            "githubRepoContext": {"startingBranch": branch},
        },
        "automationMode": "AUTO_CREATE_PR",
    }

    logger.debug("Deploying to Jules with payload: %s", payload)

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.post(url, headers=headers, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(
                        "Jules API Error: %s - %s", response.status, text
                    )
                    raise RuntimeError(
                        f"Jules API Error: {response.status} - {text}"
                    )

                return await response.json()
    except aiohttp.ClientError as e:
        logger.error("Request failed: %s", e)
        raise


async def get_session_status(session_name):
    """
    Retrieves the status of a Jules session.

    Args:
        session_name (str): The name of the session (e.g., "sessions/123").

    Returns:
        dict: The JSON response from the API.

    Raises:
        ValueError: If API keys are missing.
        RuntimeError: If the Jules API returns an error.
        aiohttp.ClientError: If the HTTP request fails.
    """
    api_key = os.environ.get("JULES_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("JULES_API_KEY or GOOGLE_API_KEY not set")

    url = f"https://jules.googleapis.com/v1alpha/{session_name}"
    headers = {"X-Goog-Api-Key": api_key, "Content-Type": "application/json"}

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as client:
            async with client.get(url, headers=headers) as response:
                if response.status != 200:
                    text = await response.text()
                    logger.error(
                        "Jules API Error: %s - %s", response.status, text
                    )
                    raise RuntimeError(
                        f"Jules API Error: {response.status} - {text}"
                    )
                return await response.json()
    except aiohttp.ClientError as e:
        logger.error("Request failed: %s", e)
        raise
