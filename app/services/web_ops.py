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
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
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
