"""Lifecycle command execution for ATK.

Handles running lifecycle commands defined in plugin.yaml.
"""

import os
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal

from atk.env import check_required_env_vars, get_env_status, load_env_file
from atk.manifest_schema import load_manifest
from atk.plugin import PluginNotFoundError, load_plugin
from atk.plugin_schema import PluginSchema

LifecycleCommand = Literal["install", "start", "stop", "logs", "status"]


# --- Result types for single plugin execution ---


@dataclass
class LifecycleSuccess:
    """Lifecycle command succeeded."""

    plugin_name: str


@dataclass
class LifecycleCommandFailed:
    """Lifecycle command ran but exited with non-zero code."""

    plugin_name: str
    exit_code: int


@dataclass
class LifecycleCommandSkipped:
    """Lifecycle command not defined in plugin."""

    plugin_name: str
    command_name: LifecycleCommand


@dataclass
class LifecyclePluginNotFound:
    """Plugin identifier not found in manifest."""

    identifier: str


@dataclass
class LifecycleMissingEnvVars:
    """Required environment variables are not set."""

    plugin_name: str
    missing_vars: list[str]


@dataclass
class PortConflict:
    """A single port conflict."""

    port: int
    description: str | None


@dataclass
class LifecyclePortConflict:
    """One or more declared ports are already in use."""

    plugin_name: str
    conflicts: list[PortConflict]


SinglePluginResult = (
    LifecycleSuccess
    | LifecycleCommandFailed
    | LifecycleCommandSkipped
    | LifecyclePluginNotFound
    | LifecycleMissingEnvVars
    | LifecyclePortConflict
)


# --- Result types for all plugins execution ---


@dataclass
class AllPluginsSuccess:
    """All plugins executed successfully (skipped is OK)."""

    succeeded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class AllPluginsPartialFailure:
    """Some plugins failed during execution."""

    succeeded: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[tuple[str, int]] = field(default_factory=list)


@dataclass
class AllPluginsMissingEnvVars:
    """Pre-flight check failed: required env vars missing."""

    plugin_name: str
    missing_vars: list[str]


@dataclass
class AllPluginsPortConflict:
    """Pre-flight check failed: port conflict detected."""

    plugin_name: str
    conflicts: list[PortConflict]


AllPluginsResult = (
    AllPluginsSuccess
    | AllPluginsPartialFailure
    | AllPluginsMissingEnvVars
    | AllPluginsPortConflict
)


class PluginStatus(str, Enum):
    """Plugin status states."""

    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class PortStatus:
    """Status of a single port."""

    port: int
    listening: bool | None  # None = not checked (plugin not running)


def is_port_listening(port: int) -> bool:
    """Check if a port is listening on localhost.

    Uses netcat (nc) to check if the port is open.

    Args:
        port: Port number to check.

    Returns:
        True if something is listening on the port, False otherwise.
    """
    result = subprocess.run(
        ["nc", "-z", "-w", "1", "localhost", str(port)],
        capture_output=True,
    )
    return result.returncode == 0


def check_port_conflicts(plugin: PluginSchema) -> list[PortConflict]:
    """Check if any declared ports are already in use.

    Args:
        plugin: The plugin schema containing port declarations.

    Returns:
        List of PortConflict for each port that is already in use.
        Empty list if no conflicts.
    """
    conflicts: list[PortConflict] = []
    for port_config in plugin.ports:
        if is_port_listening(port_config.port):
            conflicts.append(
                PortConflict(port=port_config.port, description=port_config.description)
            )
    return conflicts


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
    if plugin.lifecycle is None:
        raise LifecycleCommandNotDefinedError(command_name, plugin.name)

    command = getattr(plugin.lifecycle, command_name, None)

    if command is None:
        raise LifecycleCommandNotDefinedError(command_name, plugin.name)

    env_file = plugin_dir / ".env"
    env_from_file = load_env_file(env_file)
    merged_env = {**os.environ, **env_from_file}

    result = subprocess.run(
        command,
        shell=True,
        cwd=plugin_dir,
        env=merged_env,
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


def execute_lifecycle(
    atk_home: Path, identifier: str, command_name: LifecycleCommand
) -> SinglePluginResult:
    """Execute a lifecycle command for a single plugin with pre-flight checks.

    This is the main entry point for running lifecycle commands. It handles:
    - Loading the plugin
    - Checking required env vars (for start/install)
    - Running the command
    - Returning a typed result

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory.
        command_name: Lifecycle command to run.

    Returns:
        A SinglePluginResult indicating success or the specific failure reason.
    """
    try:
        plugin, plugin_dir = load_plugin(atk_home, identifier)
    except PluginNotFoundError:
        return LifecyclePluginNotFound(identifier=identifier)

    if command_name in ("start", "install"):
        missing = check_required_env_vars(plugin, plugin_dir)
        if missing:
            return LifecycleMissingEnvVars(plugin_name=plugin.name, missing_vars=missing)

    if command_name == "start":
        conflicts = check_port_conflicts(plugin)
        if conflicts:
            return LifecyclePortConflict(plugin_name=plugin.name, conflicts=conflicts)

    try:
        exit_code = run_lifecycle_command(plugin, plugin_dir, command_name)
    except LifecycleCommandNotDefinedError:
        return LifecycleCommandSkipped(plugin_name=plugin.name, command_name=command_name)

    if exit_code == 0:
        return LifecycleSuccess(plugin_name=plugin.name)
    else:
        return LifecycleCommandFailed(plugin_name=plugin.name, exit_code=exit_code)


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


def execute_all_lifecycle(
    atk_home: Path, command_name: LifecycleCommand, *, reverse: bool = False
) -> AllPluginsResult:
    """Execute a lifecycle command for all plugins with pre-flight checks.

    This is the main entry point for running lifecycle commands on all plugins.
    It handles:
    - Pre-flight env var checks for all plugins (fail fast on first missing)
    - Running the command on each plugin
    - Returning a typed result

    Args:
        atk_home: Path to ATK Home directory.
        command_name: Lifecycle command to run.
        reverse: If True, process plugins in reverse manifest order.

    Returns:
        An AllPluginsResult indicating success, partial failure, or pre-flight failure.
    """
    manifest = load_manifest(atk_home)
    plugins = manifest.plugins
    if reverse:
        plugins = list(reversed(plugins))

    if command_name in ("start", "install"):
        for plugin_entry in plugins:
            plugin, plugin_dir = load_plugin(atk_home, plugin_entry.directory)
            missing = check_required_env_vars(plugin, plugin_dir)
            if missing:
                return AllPluginsMissingEnvVars(
                    plugin_name=plugin.name, missing_vars=missing
                )

    if command_name == "start":
        for plugin_entry in plugins:
            plugin, _ = load_plugin(atk_home, plugin_entry.directory)
            conflicts = check_port_conflicts(plugin)
            if conflicts:
                return AllPluginsPortConflict(
                    plugin_name=plugin.name, conflicts=conflicts
                )

    succeeded: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, int]] = []

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

    if failed:
        return AllPluginsPartialFailure(
            succeeded=succeeded, skipped=skipped, failed=failed
        )
    else:
        return AllPluginsSuccess(succeeded=succeeded, skipped=skipped)


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


@dataclass
class PluginStatusResult:
    """Result of checking a plugin's status."""

    name: str
    status: PluginStatus
    ports: list[PortStatus]
    missing_required_vars: list[str]  # Names of missing required env vars
    unset_optional_count: int  # Count of unset optional env vars
    total_env_vars: int  # Total number of env vars defined in plugin.yaml


def get_plugin_status(atk_home: Path, identifier: str) -> PluginStatusResult:
    """Get the status of a single plugin.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory.

    Returns:
        PluginStatusResult with status, ports, and env var information.

    Raises:
        PluginNotFoundError: If plugin is not in the manifest.
    """
    plugin, plugin_dir = load_plugin(atk_home, identifier)

    raw_ports = [p.port for p in plugin.ports]

    # Get env var status
    env_statuses = get_env_status(plugin, plugin_dir)
    missing_required_vars = [s.name for s in env_statuses if s.required and not s.is_set]
    unset_optional_count = sum(1 for s in env_statuses if not s.required and not s.is_set)
    total_env_vars = len(env_statuses)

    if plugin.lifecycle is None or plugin.lifecycle.status is None:
        ports = [PortStatus(port=p, listening=None) for p in raw_ports]
        return PluginStatusResult(
            name=plugin.name,
            status=PluginStatus.UNKNOWN,
            ports=ports,
            missing_required_vars=missing_required_vars,
            unset_optional_count=unset_optional_count,
            total_env_vars=total_env_vars,
        )

    result = subprocess.run(
        plugin.lifecycle.status,
        shell=True,
        cwd=plugin_dir,
        capture_output=True,
    )

    status = PluginStatus.RUNNING if result.returncode == 0 else PluginStatus.STOPPED

    if status == PluginStatus.RUNNING:
        ports = [PortStatus(port=p, listening=is_port_listening(p)) for p in raw_ports]
    else:
        ports = [PortStatus(port=p, listening=None) for p in raw_ports]

    return PluginStatusResult(
        name=plugin.name,
        status=status,
        ports=ports,
        missing_required_vars=missing_required_vars,
        unset_optional_count=unset_optional_count,
        total_env_vars=total_env_vars,
    )


def get_all_plugins_status(atk_home: Path) -> list[PluginStatusResult]:
    """Get the status of all plugins.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        List of PluginStatusResult for each plugin in manifest order.
    """
    manifest = load_manifest(atk_home)
    results: list[PluginStatusResult] = []

    for plugin_entry in manifest.plugins:
        result = get_plugin_status(atk_home, plugin_entry.directory)
        results.append(result)

    return results
