"""Stop command implementation for ATK.

Handles running the stop lifecycle command for plugins.
"""

from pathlib import Path

from atk.lifecycle import (
    LifecycleResult,
    run_all_plugins_lifecycle,
    run_plugin_lifecycle,
)


def stop_plugin(atk_home: Path, identifier: str) -> int:
    """Run the stop lifecycle command for a plugin.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory to stop.

    Returns:
        Exit code from the stop command.

    Raises:
        PluginNotFoundError: If plugin is not in the manifest.
        LifecycleCommandNotDefinedError: If stop command is not defined.
    """
    return run_plugin_lifecycle(atk_home, identifier, "stop")


def stop_all_plugins(atk_home: Path) -> LifecycleResult:
    """Run the stop lifecycle command for all plugins.

    Stops plugins in REVERSE manifest order. Continues on failure.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        LifecycleResult with lists of succeeded, failed, and skipped plugins.
    """
    return run_all_plugins_lifecycle(atk_home, "stop", reverse=True)

