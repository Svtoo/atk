"""Lifecycle command execution for ATK.

Handles running lifecycle commands defined in plugin.yaml.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from atk.manifest_schema import load_manifest
from atk.plugin import load_plugin
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


@dataclass
class RestartAllResult:
    """Result of running restart --all.

    Unlike other lifecycle commands, restart --all is a two-phase operation:
    1. Stop all plugins (reverse order)
    2. Start all plugins (manifest order)

    This result tracks both phases separately.
    """

    stop_result: LifecycleResult
    start_result: LifecycleResult | None  # None if stop phase had failures

    @property
    def stop_succeeded(self) -> list[str]:
        """Plugins that stopped successfully."""
        return self.stop_result.succeeded

    @property
    def stop_failed(self) -> list[tuple[str, int]]:
        """Plugins that failed to stop."""
        return self.stop_result.failed

    @property
    def stop_skipped(self) -> list[str]:
        """Plugins skipped during stop (no stop command)."""
        return self.stop_result.skipped

    @property
    def start_succeeded(self) -> list[str]:
        """Plugins that started successfully."""
        if self.start_result is None:
            return []
        return self.start_result.succeeded

    @property
    def start_failed(self) -> list[tuple[str, int]]:
        """Plugins that failed to start."""
        if self.start_result is None:
            return []
        return self.start_result.failed

    @property
    def start_skipped(self) -> list[str]:
        """Plugins skipped during start (no start command)."""
        if self.start_result is None:
            return []
        return self.start_result.skipped

    @property
    def all_succeeded(self) -> bool:
        """Return True if both stop and start phases succeeded."""
        if not self.stop_result.all_succeeded:
            return False
        if self.start_result is None:
            return False
        return self.start_result.all_succeeded


def restart_all_plugins(atk_home: Path) -> RestartAllResult:
    """Restart all plugins by stopping then starting them.

    This is a two-phase operation:
    1. Stop all plugins in REVERSE manifest order
    2. Start all plugins in manifest order

    If the stop phase has any failures, the start phase is skipped.
    This is a safety measure - we don't want to start plugins if we
    couldn't cleanly stop them.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        RestartAllResult with stop and start phase results.
    """
    # Phase 1: Stop all in reverse order
    stop_result = run_all_plugins_lifecycle(atk_home, "stop", reverse=True)

    # If stop phase had failures, skip start phase
    if not stop_result.all_succeeded:
        return RestartAllResult(stop_result=stop_result, start_result=None)

    # Phase 2: Start all in manifest order
    start_result = run_all_plugins_lifecycle(atk_home, "start")

    return RestartAllResult(stop_result=stop_result, start_result=start_result)

