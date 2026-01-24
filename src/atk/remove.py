"""Plugin remove functionality for ATK.

Handles removing plugins from ATK Home.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from atk.git import git_add, git_commit
from atk.home import validate_atk_home
from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import load_manifest, save_manifest
from atk.plugin import load_plugin_schema


@dataclass
class RemoveResult:
    """Result of removing a plugin."""

    removed: bool
    stop_failed: bool = False
    stop_exit_code: int | None = None


def remove_plugin(identifier: str, atk_home: Path) -> RemoveResult:
    """Remove a plugin from ATK Home.

    Runs the stop lifecycle command before removing files (if defined).
    Continues with removal even if stop fails.

    Args:
        identifier: Plugin identifier - can be directory name or plugin name.
        atk_home: Path to ATK Home directory.

    Returns:
        RemoveResult with removed status and stop lifecycle info.

    Raises:
        ValueError: If ATK Home is not initialized.
    """
    # Validate ATK Home is initialized
    validation = validate_atk_home(atk_home)
    if not validation.is_valid:
        msg = f"ATK Home '{atk_home}' is not initialized: {', '.join(validation.errors)}"
        raise ValueError(msg)

    # Check if plugin exists in manifest
    manifest = load_manifest(atk_home)

    # Find plugin in manifest by directory OR name
    plugin_entry = next(
        (p for p in manifest.plugins if p.directory == identifier or p.name == identifier),
        None,
    )

    if plugin_entry is None:
        # Plugin not found - no-op (idempotent)
        return RemoveResult(removed=False)

    # Capture plugin name before removal for commit message
    plugin_name = plugin_entry.name
    auto_commit = manifest.config.auto_commit

    # Get plugin directory
    plugin_dir = atk_home / "plugins" / plugin_entry.directory

    # Run stop lifecycle command if defined
    stop_failed = False
    stop_exit_code = None
    if plugin_dir.exists():
        try:
            schema = load_plugin_schema(plugin_dir)
            exit_code = run_lifecycle_command(schema, plugin_dir, "stop")
            if exit_code != 0:
                stop_failed = True
                stop_exit_code = exit_code
        except LifecycleCommandNotDefinedError:
            # Skip silently - stop is optional
            pass

    # Remove plugin directory if it exists
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)

    # Remove from manifest
    manifest.plugins = [p for p in manifest.plugins if p.directory != plugin_entry.directory]

    # Write updated manifest
    save_manifest(manifest, atk_home)

    # Commit changes if auto_commit is enabled
    if auto_commit:
        git_add(atk_home)
        git_commit(atk_home, f"Remove plugin '{plugin_name}'")

    return RemoveResult(removed=True, stop_failed=stop_failed, stop_exit_code=stop_exit_code)

