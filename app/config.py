"""
Configuration module for the backend.
Handles environment variables and client initialization.
"""

import os
import logging
import json
from google import genai

logger = logging.getLogger(__name__)

# Environment Variables
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
ENABLE_GOOGLE_SEARCH = os.environ.get("ENABLE_GOOGLE_SEARCH", "false").lower() in (
    "true",
    "1",
    "yes",
)

# Application Constants
HISTORY_LIMIT = 20
DEFAULT_MODEL = "gemini-3-pro-preview"

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY environment variable not set.")

# Initialize client
try:
    CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to initialize Gemini client: %s", e)
    CLIENT = None


def get_mcp_servers():
    """
    Reads mcp_servers.json from the root directory and returns the configuration.
    Returns an empty dict if the file does not exist.
    """
    mcp_config_path = os.path.join(os.getcwd(), "mcp_servers.json")
    if not os.path.exists(mcp_config_path):
        return {}

    try:
        with open(mcp_config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse mcp_servers.json: %s", e)
        return {}
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error reading mcp_servers.json: %s", e)
        return {}
