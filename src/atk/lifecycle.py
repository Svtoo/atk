"""Lifecycle command execution for ATK.

Handles running lifecycle commands defined in plugin.yaml.
"""

import subprocess
from pathlib import Path
from typing import Literal

from atk.plugin_schema import PluginSchema

# Valid lifecycle command names matching LifecycleConfig fields
LifecycleCommand = Literal["install", "start", "stop", "restart", "logs", "status"]


class LifecycleCommandNotDefinedError(Exception):
    """Raised when a lifecycle command is not defined in the plugin."""

    def __init__(self, command_name: LifecycleCommand, plugin_name: str) -> None:
        """Initialize with the command name and plugin name."""
        self.command_name = command_name
        self.plugin_name = plugin_name
        super().__init__(
            f"Lifecycle command '{command_name}' not defined in plugin '{plugin_name}'"
        )


def run_lifecycle_command(
    plugin: PluginSchema, plugin_dir: Path, command_name: LifecycleCommand
) -> int:
    """Execute a lifecycle command from the plugin.

    Args:
        plugin: The plugin schema containing lifecycle configuration.
        plugin_dir: Path to the plugin directory (used as cwd).
        command_name: Name of the lifecycle command to run.

    Returns:
        Exit code from the command.

    Raises:
        LifecycleCommandNotDefinedError: If the command is not defined in the plugin.
    """
    # Check if lifecycle section exists
    if plugin.lifecycle is None:
        raise LifecycleCommandNotDefinedError(command_name, plugin.name)

    # Get the command from lifecycle config
    command = getattr(plugin.lifecycle, command_name, None)

    if command is None:
        raise LifecycleCommandNotDefinedError(command_name, plugin.name)

    # Run the command in the plugin directory
    result = subprocess.run(
        command,
        shell=True,
        cwd=plugin_dir,
    )

    return result.returncode

