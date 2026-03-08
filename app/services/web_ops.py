"""
Service for fetching and parsing web content.
"""

import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def fetch_url(url: str) -> str:
    """
    Fetches the content of a URL and extracts the text content.
    Returns the text content or a user-friendly error message if it fails.

    Args:
        url (str): The URL to fetch.
    Returns:
        str: The extracted text or an error message.
    """
    try:
        response = requests.get(url, timeout=10, stream=True)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "").lower()
        allowed_types = (
            "text/html",
            "text/plain",
            "text/markdown",
            "application/json",
            "application/xml",
        )

        is_allowed = False
        for allowed in allowed_types:
            if content_type.startswith(allowed):
                is_allowed = True
                break

        if not is_allowed:
            response.close()
            return (
                "Error: Downloading files is strictly forbidden. "
                "The browser tool is only for viewing text-based web pages."
            )

        # Implement a 5MB read size limit
        max_size = 5 * 1024 * 1024
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content += chunk
                if len(content) > max_size:
                    logger.warning("URL %s exceeded 5MB size limit. Truncating.", url)
                    break

        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        return text
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching URL: %s", url)
        return f"Error: Request to {url} timed out."
    except requests.exceptions.ConnectionError:
        logger.error("Connection error fetching URL: %s", url)
        return f"Error: Failed to connect to {url}."
    except requests.exceptions.RequestException as e:
        logger.error("Error fetching URL: %s, Exception: %s", url, e)
        return f"Error: Failed to fetch {url}. Exception: {e}"
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Unexpected error parsing URL: %s, Exception: %s", url, e)
        return f"Error: Unexpected error processing {url}. Exception: {e}"
