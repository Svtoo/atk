"""Bootstrap fetch for missing plugins.

When a plugin is declared in the manifest but its files are not on disk
(e.g. fresh clone of ATK Home on a new machine), this module fetches the
plugin from its source (registry or git) so that lifecycle commands can run.

Local plugins are never fetched — they must already exist on disk.
"""

import shutil
import tempfile
from pathlib import Path

from atk.fetch import fetch_plugin_source
from atk.git import write_atk_ref
from atk.manifest_schema import PluginEntry, SourceType
from atk.plugin import CUSTOM_DIR


class BootstrapError(Exception):
    """Raised when fetching a missing plugin fails."""


def plugin_needs_pull(plugin_dir: Path) -> bool:
    """Check whether a plugin directory is missing its plugin.yaml.

    A plugin "needs pull" when:
    - The directory does not exist at all, OR
    - The directory exists but contains no plugin.yaml / plugin.yml
      (e.g. only a custom/ directory synced via git).

    Returns True if the plugin files should be fetched from the source.
    """
    if not plugin_dir.exists():
        return True
    return not (plugin_dir / "plugin.yaml").exists() and not (plugin_dir / "plugin.yml").exists()


def fetch_missing_plugin(plugin_entry: PluginEntry, atk_home: Path) -> None:
    """Fetch plugin files from the declared source if they are missing.

    For registry sources, fetches from the ATK registry.
    For git sources, fetches from the stored URL.
    For local sources, raises BootstrapError (local plugins must exist).

    Preserves any existing custom/ directory (e.g. user overrides synced
    via git before the plugin files were pulled).

    Args:
        plugin_entry: The manifest entry for the plugin.
        atk_home: Path to ATK Home directory.

    Raises:
        BootstrapError: If the source type is local or fetching fails.
    """
    plugin_dir = atk_home / "plugins" / plugin_entry.directory

    if not plugin_needs_pull(plugin_dir):
        return

    source = plugin_entry.source

    if source.type == SourceType.LOCAL:
        msg = (
            f"Plugin '{plugin_entry.name}' is local but its files are missing. "
            f"Local plugins cannot be fetched — restore the files manually."
        )
        raise BootstrapError(msg)

    if not source.ref:
        msg = (
            f"Plugin '{plugin_entry.name}' has no pinned ref in manifest. "
            f"Cannot fetch without a commit hash."
        )
        raise BootstrapError(msg)

    with tempfile.TemporaryDirectory() as tmp:
        staging_dir = Path(tmp) / "staging"
        fetched_ref = fetch_plugin_source(
            source_type=source.type,
            directory=plugin_entry.directory,
            target_dir=staging_dir,
            ref=source.ref,
            source_url=source.url,
        )
        _install_fetched_files(plugin_dir, staging_dir)

    write_atk_ref(plugin_dir, fetched_ref)


def _install_fetched_files(plugin_dir: Path, staging_dir: Path) -> None:
    """Copy fetched files into the plugin directory, preserving custom/.

    If the plugin directory already exists (e.g. with a custom/ subdirectory),
    copies each item from staging individually, skipping custom/.
    If the plugin directory does not exist, copies the entire staging directory.
    """
    if not plugin_dir.exists():
        shutil.copytree(staging_dir, plugin_dir)
        return

    # Directory exists (likely has custom/) — merge without overwriting custom/
    for item in staging_dir.iterdir():
        if item.name == CUSTOM_DIR:
            continue
        dest = plugin_dir / item.name
        if item.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

