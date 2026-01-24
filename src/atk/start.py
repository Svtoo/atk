"""Start command implementation for ATK.

Handles running the start lifecycle command for plugins.
"""

from pathlib import Path

from atk.lifecycle import (
    LifecycleResult,
    run_all_plugins_lifecycle,
    run_plugin_lifecycle,
)


def start_plugin(atk_home: Path, identifier: str) -> int:
    """Run the start lifecycle command for a plugin.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory to start.

    Returns:
        Exit code from the start command.

    Raises:
        PluginNotFoundError: If plugin is not in the manifest.
        LifecycleCommandNotDefinedError: If start command is not defined.
    """
    return run_plugin_lifecycle(atk_home, identifier, "start")


def start_all_plugins(atk_home: Path) -> LifecycleResult:
    """Run the start lifecycle command for all plugins.

    Starts plugins in manifest order. Continues on failure.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        LifecycleResult with lists of succeeded, failed, and skipped plugins.
    """
    return run_all_plugins_lifecycle(atk_home, "start")

