"""Install command implementation for ATK.

Handles running the install lifecycle command for plugins.
"""

from dataclasses import dataclass
from pathlib import Path

from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import load_manifest
from atk.plugin import load_plugin


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
    plugin, plugin_dir = load_plugin(atk_home, identifier)
    return run_lifecycle_command(plugin, plugin_dir, "install")


@dataclass
class InstallAllResult:
    """Result of installing all plugins."""

    succeeded: list[str]
    failed: list[tuple[str, int]]
    skipped: list[str]

    @property
    def all_succeeded(self) -> bool:
        """Return True if all plugins installed successfully (skipped is OK)."""
        return len(self.failed) == 0


def install_all_plugins(atk_home: Path) -> InstallAllResult:
    """Run the install lifecycle command for all plugins.

    Installs plugins in manifest order. Continues on failure.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        InstallAllResult with lists of succeeded, failed, and skipped plugins.
    """
    manifest = load_manifest(atk_home)
    succeeded: list[str] = []
    failed: list[tuple[str, int]] = []
    skipped: list[str] = []

    for plugin_entry in manifest.plugins:
        try:
            exit_code = install_plugin(atk_home, plugin_entry.directory)
            if exit_code == 0:
                succeeded.append(plugin_entry.name)
            else:
                failed.append((plugin_entry.name, exit_code))
        except LifecycleCommandNotDefinedError:
            skipped.append(plugin_entry.name)

    return InstallAllResult(succeeded=succeeded, failed=failed, skipped=skipped)

