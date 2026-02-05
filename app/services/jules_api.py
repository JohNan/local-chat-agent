"""
Service module for interacting with the Jules API.
"""

import logging
import os
import httpx

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
        httpx.HTTPError: If the HTTP request fails.
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
    }

    logger.debug("Deploying to Jules with payload: %s", payload)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30)

        if response.status_code != 200:
            logger.error(
                "Jules API Error: %s - %s", response.status_code, response.text
            )
            raise RuntimeError(
                f"Jules API Error: {response.status_code} - {response.text}"
            )

        return response.json()
    except httpx.HTTPError as e:
        logger.error("Request failed: %s", e)
        raise
