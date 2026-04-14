"""Configuration management for ATK.

Handles resolution of configuration values from environment variables
and config files with proper precedence order.
"""

import os
from pathlib import Path
from typing import Any

import yaml

# Environment variable for custom registry URL
ATK_REGISTRY_URL = "ATK_REGISTRY_URL"

# Default registry URL
DEFAULT_REGISTRY_URL = "https://github.com/Svtoo/atk-registry"


def load_config_file(atk_home: Path) -> dict[str, Any]:
    """Load configuration from ~/.atk/config.yaml.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        Dictionary of configuration values. Returns empty dict if file doesn't exist.
    """
    config_path = atk_home / "config.yaml"
    if not config_path.exists():
        return {}

    try:
        content = config_path.read_text()
        return yaml.safe_load(content) or {}
    except (yaml.YAMLError, OSError):
        # If config file is malformed, ignore it and use defaults
        return {}


def get_registry_url(atk_home: Path) -> str:
    """Get the registry URL with proper precedence order.

    Resolution order:
    1. ATK_REGISTRY_URL environment variable (if set)
    2. registry_url from ~/.atk/config.yaml (if exists)
    3. Default hardcoded URL

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        Registry URL to use.
    """
    # 1. Environment variable takes precedence
    env_value = os.environ.get(ATK_REGISTRY_URL)
    if env_value:
        return env_value

    # 2. Config file
    config = load_config_file(atk_home)
    config_url: str | None = config.get("registry_url")
    if config_url:
        return config_url

    # 3. Default fallback
    return DEFAULT_REGISTRY_URL
