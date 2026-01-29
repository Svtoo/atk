"""Environment variable management for ATK plugins."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values

from atk.plugin_schema import PluginSchema


@dataclass
class EnvVarStatus:
    """Status of an environment variable."""

    name: str
    required: bool
    secret: bool
    is_set: bool
    value: str | None


def load_env_file(path: Path) -> dict[str, str]:
    """Load environment variables from a .env file.

    Args:
        path: Path to the .env file.

    Returns:
        Dictionary of environment variable names to values.
        Returns empty dict if file doesn't exist.
    """
    if not path.exists():
        return {}

    raw_values = dotenv_values(path)
    return {k: v for k, v in raw_values.items() if v is not None}


def save_env_file(
    path: Path,
    env_vars: dict[str, str],
    descriptions: dict[str, str] | None = None,
) -> None:
    """Save environment variables to a .env file.

    Args:
        path: Path to the .env file.
        env_vars: Dictionary of environment variable names to values.
        descriptions: Optional dictionary of variable names to descriptions.
            If provided, descriptions are written as comments above each variable.
    """
    descriptions = descriptions or {}
    lines: list[str] = []

    for key, value in env_vars.items():
        # Add description as comment if available
        if key in descriptions:
            lines.append(f"# {descriptions[key]}")

        # Quote values containing spaces
        if " " in value:
            value = f'"{value}"'
        lines.append(f"{key}={value}")

    path.write_text("\n".join(lines) + "\n" if lines else "")


def get_env_status(plugin: PluginSchema, plugin_dir: Path) -> list[EnvVarStatus]:
    """Get the status of all environment variables for a plugin.

    Checks both the plugin's .env file and the system environment.
    The .env file takes precedence over system environment.

    Args:
        plugin: The plugin schema.
        plugin_dir: Path to the plugin directory.

    Returns:
        List of EnvVarStatus for each env var defined in the plugin.
    """
    if not plugin.env_vars:
        return []

    # Load .env file
    env_file = plugin_dir / ".env"
    file_vars = load_env_file(env_file)

    result: list[EnvVarStatus] = []

    for env_var in plugin.env_vars:
        # Check .env file first, then system environment
        if env_var.name in file_vars:
            value = file_vars[env_var.name]
            is_set = True
        elif env_var.name in os.environ:
            value = os.environ[env_var.name]
            is_set = True
        else:
            value = None
            is_set = False

        result.append(
            EnvVarStatus(
                name=env_var.name,
                required=env_var.required,
                secret=env_var.secret,
                is_set=is_set,
                value=value,
            )
        )

    return result

