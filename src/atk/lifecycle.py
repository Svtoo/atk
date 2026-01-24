"""Lifecycle command execution for ATK.

Handles running lifecycle commands defined in plugin.yaml.
"""

import subprocess
from dataclasses import dataclass
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


@dataclass
class LifecycleResult:
    """Result of running a lifecycle command on multiple plugins."""

    succeeded: list[str]
    failed: list[tuple[str, int]]
    skipped: list[str]

    @property
    def all_succeeded(self) -> bool:
        """Return True if all plugins succeeded (skipped is OK)."""
        return len(self.failed) == 0


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


def run_plugin_lifecycle(
    atk_home: Path, identifier: str, command_name: LifecycleCommand
) -> int:
    """Run a lifecycle command for a single plugin.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory.
        command_name: Lifecycle command to run.

    Returns:
        Exit code from the command.

    Raises:
        PluginNotFoundError: If plugin is not in the manifest.
        LifecycleCommandNotDefinedError: If command is not defined.
    """
    # Import here to avoid circular dependency
    from atk.plugin import load_plugin

    plugin, plugin_dir = load_plugin(atk_home, identifier)
    return run_lifecycle_command(plugin, plugin_dir, command_name)


def run_all_plugins_lifecycle(
    atk_home: Path, command_name: LifecycleCommand, *, reverse: bool = False
) -> LifecycleResult:
    """Run a lifecycle command for all plugins.

    Args:
        atk_home: Path to ATK Home directory.
        command_name: Lifecycle command to run.
        reverse: If True, process plugins in reverse manifest order.

    Returns:
        LifecycleResult with succeeded, failed, and skipped plugins.
    """
    # Import here to avoid circular dependency
    from atk.manifest_schema import load_manifest

    manifest = load_manifest(atk_home)
    succeeded: list[str] = []
    failed: list[tuple[str, int]] = []
    skipped: list[str] = []

    plugins = manifest.plugins
    if reverse:
        plugins = list(reversed(plugins))

    for plugin_entry in plugins:
        try:
            exit_code = run_plugin_lifecycle(
                atk_home, plugin_entry.directory, command_name
            )
            if exit_code == 0:
                succeeded.append(plugin_entry.name)
            else:
                failed.append((plugin_entry.name, exit_code))
        except LifecycleCommandNotDefinedError:
            skipped.append(plugin_entry.name)

    return LifecycleResult(succeeded=succeeded, failed=failed, skipped=skipped)

