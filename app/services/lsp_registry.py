"""
Service for managing LSP server configurations.
"""
import json
import logging
import os
import shutil
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

CATALOG_PATH = os.path.join(os.path.dirname(__file__), "../lsp/catalog.json")

class LSPRegistry:
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LSPRegistry, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """Loads and verifies LSP configurations from the catalog."""
        if not os.path.exists(CATALOG_PATH):
            logger.error("LSP catalog not found at %s", CATALOG_PATH)
            return

        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                raw_config = json.load(f)

            for lang, config in raw_config.items():
                bin_name = config.get("bin")
                if not bin_name:
                    logger.warning("LSP config for %s missing 'bin'", lang)
                    continue

                if shutil.which(bin_name):
                    self._config[lang] = config
                    logger.info("LSP server for %s found: %s", lang, bin_name)
                else:
                    logger.warning("LSP binary '%s' for %s not found in PATH", bin_name, lang)

        except json.JSONDecodeError as e:
            logger.error("Failed to parse LSP catalog: %s", e)
        except Exception as e:
            logger.error("Error loading LSP registry: %s", e)

    def get_config_by_extension(self, ext: str) -> Optional[Dict[str, Any]]:
        """
        Returns the LSP configuration for a given file extension.
        """
        for config in self._config.values():
            if ext in config.get("extensions", []):
                return config
        return None
