import os
import requests
import logging

logger = logging.getLogger(__name__)


def deploy_to_jules(prompt_text, repo_info):
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

    logger.debug(f"Deploying to Jules with payload: {payload}")

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            logger.error(f"Jules API Error: {response.status_code} - {response.text}")
            raise Exception(
                f"Jules API Error: {response.status_code} - {response.text}"
            )

        return response.json()
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise
