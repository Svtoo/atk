"""Plugin upgrade functionality for ATK.

Handles upgrading registry and git plugins to the latest remote version.
Local plugins cannot be upgraded (they are managed outside ATK).
"""

import filecmp
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import atk.registry as registry_mod
from atk.git import git_add, git_commit, git_ls_remote, read_atk_ref, write_atk_ref
from atk.git_source import fetch_git_plugin, normalize_git_url
from atk.home import validate_atk_home
from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import SourceType, load_manifest, save_manifest
from atk.plugin import load_plugin_schema
from atk.plugin_schema import PluginSchema
from atk.setup import run_setup


class UpgradeError(Exception):
    """Raised when an upgrade operation fails."""


class LocalPluginError(UpgradeError):
    """Raised when attempting to upgrade a local plugin."""


@dataclass
class UpgradeResult:
    """Result of upgrading a plugin."""

    plugin_name: str
    upgraded: bool
    old_ref: str | None = None
    new_ref: str | None = None
    new_env_vars: list[str] = field(default_factory=list)
    install_failed: bool = False
    install_exit_code: int | None = None


def _get_remote_url(source_type: SourceType, source_url: str) -> str:
    """Get the git URL to check for updates.

    For registry plugins, this is the registry repo URL.
    For git plugins, this is the stored source URL (normalized).
    """
    if source_type == SourceType.REGISTRY:
        return registry_mod.REGISTRY_URL
    return normalize_git_url(source_url)


def _get_current_ref(plugin_dir: Path, manifest_ref: str | None) -> str | None:
    """Get the current on-disk ref, preferring .atk-ref over manifest."""
    return read_atk_ref(plugin_dir) or manifest_ref


def _detect_new_env_vars(
    old_schema: PluginSchema, new_schema: PluginSchema,
) -> list[str]:
    """Find env var names present in new schema but not in old."""
    old_names = {v.name for v in old_schema.env_vars}
    return [v.name for v in new_schema.env_vars if v.name not in old_names]


def _build_filtered_schema(schema: PluginSchema, var_names: list[str]) -> PluginSchema:
    """Create a copy of the schema with only the specified env vars."""
    filtered_vars = [v for v in schema.env_vars if v.name in var_names]
    return schema.model_copy(update={"env_vars": filtered_vars})


CUSTOM_DIR = "custom"


def _preserve_custom(plugin_dir: Path, backup_dir: Path) -> bool:
    """Back up the custom/ directory if it exists. Returns True if backed up."""
    custom_dir = plugin_dir / CUSTOM_DIR
    if custom_dir.is_dir():
        shutil.copytree(custom_dir, backup_dir / CUSTOM_DIR)
        return True
    return False


def _restore_custom(plugin_dir: Path, backup_dir: Path) -> None:
    """Restore the custom/ directory from backup."""
    backup_custom = backup_dir / CUSTOM_DIR
    if backup_custom.is_dir():
        target_custom = plugin_dir / CUSTOM_DIR
        if target_custom.exists():
            shutil.rmtree(target_custom)
        shutil.copytree(backup_custom, target_custom)


IGNORED_FILES = {".atk-ref"}


def _plugin_content_changed(current_dir: Path, staging_dir: Path) -> bool:
    """Check if plugin content differs between current and staged versions.

    Compares all files except .atk-ref and custom/ directory.
    Returns True if there are differences.
    """
    ignore = [CUSTOM_DIR, *IGNORED_FILES]
    comparison = filecmp.dircmp(current_dir, staging_dir, ignore=ignore)
    return _dircmp_has_diff(comparison)


def _dircmp_has_diff(comparison: filecmp.dircmp[str]) -> bool:
    """Recursively check if a dircmp shows any differences."""
    if comparison.left_only or comparison.right_only or comparison.diff_files:
        return True
    return any(_dircmp_has_diff(sub) for sub in comparison.subdirs.values())


def _fetch_to_staging(
    source_type: SourceType,
    source_url: str,
    directory: str,
    staging_dir: Path,
) -> str:
    """Fetch the latest plugin version to a staging directory.

    For registry plugins, directory is the registry slug name.
    Returns the new commit hash.
    """
    if source_type == SourceType.REGISTRY:
        registry_result = registry_mod.fetch_registry_plugin(
            name=directory, target_dir=staging_dir,
        )
        return registry_result.commit_hash

    git_result = fetch_git_plugin(url=source_url, target_dir=staging_dir)
    return git_result.commit_hash


def _replace_plugin_files(plugin_dir: Path, staging_dir: Path) -> None:
    """Replace plugin directory contents with staged files."""
    shutil.rmtree(plugin_dir)
    shutil.copytree(staging_dir, plugin_dir)


def upgrade_plugin(
    identifier: str,
    atk_home: Path,
    prompt_func: Callable[[str], str],
) -> UpgradeResult:
    """Upgrade a plugin to the latest remote version.

    Checks the remote for a newer commit, fetches if needed, preserves
    the custom/ directory, detects new env vars, runs setup and install.

    Args:
        identifier: Plugin identifier — can be directory name or plugin name.
        atk_home: Path to ATK Home directory.
        prompt_func: Function for prompting user input (for new env vars).

    Returns:
        UpgradeResult with upgrade status and details.

    Raises:
        ValueError: If ATK Home is not initialized.
        LocalPluginError: If the plugin is a local source.
        UpgradeError: If the upgrade fails for other reasons.
    """
    validation = validate_atk_home(atk_home)
    if not validation.is_valid:
        msg = f"ATK Home '{atk_home}' is not initialized: {', '.join(validation.errors)}"
        raise ValueError(msg)

    manifest = load_manifest(atk_home)

    plugin_entry = next(
        (p for p in manifest.plugins if p.directory == identifier or p.name == identifier),
        None,
    )
    if plugin_entry is None:
        msg = f"Plugin '{identifier}' not found in manifest"
        raise UpgradeError(msg)

    if plugin_entry.source.type == SourceType.LOCAL:
        msg = f"Plugin '{plugin_entry.name}' is a local plugin and cannot be upgraded"
        raise LocalPluginError(msg)

    source_url = plugin_entry.source.url or ""
    if plugin_entry.source.type == SourceType.GIT and not source_url:
        msg = f"Git plugin '{plugin_entry.name}' has no source URL in manifest"
        raise UpgradeError(msg)

    plugin_dir = atk_home / "plugins" / plugin_entry.directory
    old_schema = load_plugin_schema(plugin_dir)
    current_ref = _get_current_ref(plugin_dir, plugin_entry.source.ref)

    # Quick check: if remote HEAD hasn't changed, plugin is definitely up to date
    remote_url = _get_remote_url(plugin_entry.source.type, source_url)
    latest_ref = git_ls_remote(remote_url)
    if current_ref == latest_ref:
        return UpgradeResult(
            plugin_name=plugin_entry.name,
            upgraded=False,
            old_ref=current_ref,
            new_ref=latest_ref,
        )

    # HEAD changed — fetch to staging and check if plugin content actually changed
    with tempfile.TemporaryDirectory() as tmp:
        staging_dir = Path(tmp) / "staging"
        backup_dir = Path(tmp) / "backup"
        backup_dir.mkdir()

        new_ref = _fetch_to_staging(
            plugin_entry.source.type,
            source_url,
            plugin_entry.directory,
            staging_dir,
        )

        if not _plugin_content_changed(plugin_dir, staging_dir):
            # Repo HEAD changed but plugin directory content is identical.
            # Update stored ref to avoid re-fetching next time.
            write_atk_ref(plugin_dir, new_ref)
            plugin_entry.source.ref = new_ref
            save_manifest(manifest, atk_home)
            return UpgradeResult(
                plugin_name=plugin_entry.name,
                upgraded=False,
                old_ref=current_ref,
                new_ref=new_ref,
            )

        new_schema = load_plugin_schema(staging_dir)
        new_env_var_names = _detect_new_env_vars(old_schema, new_schema)

        _preserve_custom(plugin_dir, backup_dir)
        _replace_plugin_files(plugin_dir, staging_dir)
        _restore_custom(plugin_dir, backup_dir)

    write_atk_ref(plugin_dir, new_ref)

    if new_env_var_names:
        filtered_schema = _build_filtered_schema(new_schema, new_env_var_names)
        run_setup(filtered_schema, plugin_dir, prompt_func)

    install_failed = False
    install_exit_code = None
    try:
        exit_code = run_lifecycle_command(new_schema, plugin_dir, "install")
        if exit_code != 0:
            install_failed = True
            install_exit_code = exit_code
    except LifecycleCommandNotDefinedError:
        pass

    plugin_entry.source.ref = new_ref
    save_manifest(manifest, atk_home)

    if manifest.config.auto_commit:
        git_add(atk_home)
        git_commit(atk_home, f"Upgrade plugin '{plugin_entry.name}'")

    return UpgradeResult(
        plugin_name=plugin_entry.name,
        upgraded=True,
        old_ref=current_ref,
        new_ref=new_ref,
        new_env_vars=new_env_var_names,
        install_failed=install_failed,
        install_exit_code=install_exit_code,
    )

