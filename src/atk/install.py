"""Install command implementation for ATK.

Handles running the install lifecycle command for plugins.
"""

from pathlib import Path

from atk.lifecycle import (
    LifecycleResult,
    run_all_plugins_lifecycle,
    run_plugin_lifecycle,
)


def install_plugin(atk_home: Path, identifier: str) -> int:
    """Run the install lifecycle command for a plugin.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory to install.

    Returns:
        Exit code from the install command.

    Raises:
        PluginNotFoundError: If plugin is not in the manifest.
        LifecycleCommandNotDefinedError: If install command is not defined.
    """
    return run_plugin_lifecycle(atk_home, identifier, "install")


def install_all_plugins(atk_home: Path) -> LifecycleResult:
    """Run the install lifecycle command for all plugins.

    Installs plugins in manifest order. Continues on failure.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        LifecycleResult with lists of succeeded, failed, and skipped plugins.
    """
    return run_all_plugins_lifecycle(atk_home, "install")

