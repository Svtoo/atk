"""Plugin remove functionality for ATK.

Handles removing plugins from ATK Home.
"""

import shutil
from pathlib import Path

from atk.git import git_add, git_commit
from atk.home import validate_atk_home
from atk.manifest_schema import load_manifest, save_manifest


def remove_plugin(identifier: str, atk_home: Path) -> bool:
    """Remove a plugin from ATK Home.

    Args:
        identifier: Plugin identifier - can be directory name or plugin name.
        atk_home: Path to ATK Home directory.

    Returns:
        True if plugin was removed, False if plugin was not found (no-op).

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
        return False

    # Capture plugin name before removal for commit message
    plugin_name = plugin_entry.name
    auto_commit = manifest.config.auto_commit

    # Remove plugin directory if it exists
    plugin_dir = atk_home / "plugins" / plugin_entry.directory
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

    return True

