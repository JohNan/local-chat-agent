"""
Configuration module for the backend.
Handles environment variables and client initialization.
"""

import os
import logging
from google import genai

logger = logging.getLogger(__name__)

# Environment Variables
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
ENABLE_GOOGLE_SEARCH = os.environ.get("ENABLE_GOOGLE_SEARCH", "false").lower() in (
    "true",
    "1",
    "yes",
)

if not GOOGLE_API_KEY:
    logger.warning("Warning: GOOGLE_API_KEY environment variable not set.")

# Initialize client
try:
    CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to initialize Gemini client: %s", e)
    CLIENT = None
