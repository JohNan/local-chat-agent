"""
Shared storage utilities for managing file paths.
"""

import os


def get_storage_path(env_var_name: str, filename: str) -> str:
    """
    Determines the storage path based on priority:
    1. Environment variable
    2. /config directory (if exists and writable)
    3. Local file (fallback)
    """
    # Priority 1: Environment variable
    env_path = os.environ.get(env_var_name)
    if env_path:
        return env_path

    # Priority 2: /config directory
    config_dir = "/config"
    # Check if /config exists, is a directory, and is writable
    if (
        os.path.exists(config_dir)
        and os.path.isdir(config_dir)
        and os.access(config_dir, os.W_OK)
    ):
        return os.path.join(config_dir, filename)

    # Fallback: Local file
    return filename
