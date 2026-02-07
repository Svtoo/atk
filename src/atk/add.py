"""Plugin add functionality for ATK.

Handles adding plugins from local directories, single YAML files, or the registry.
"""

import shutil
import tempfile
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from atk.git import add_gitignore_exemption, git_add, git_commit, write_atk_ref
from atk.git_source import fetch_git_plugin
from atk.home import validate_atk_home
from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import PluginEntry, SourceInfo, SourceType, load_manifest, save_manifest
from atk.plugin import load_plugin_schema
from atk.plugin_schema import PluginSchema
from atk.registry import fetch_registry_plugin
from atk.sanitize import sanitize_directory_name
from atk.setup import run_setup
from atk.source import resolve_source


class InstallFailedError(Exception):
    """Raised when the install lifecycle command fails."""

    def __init__(self, plugin_name: str, exit_code: int) -> None:
        """Initialize with the plugin name and exit code."""
        self.plugin_name = plugin_name
        self.exit_code = exit_code
        super().__init__(
            f"Install lifecycle command failed for plugin '{plugin_name}' with exit code {exit_code}"
        )


class AddSourceType(str, Enum):
    """Type of plugin source for add command (directory or file)."""

    DIRECTORY = "directory"
    FILE = "file"


def detect_source_type(source: Path) -> AddSourceType:
    """Detect whether the source is a directory or single file.

    Args:
        source: Path to the plugin source (directory or file).

    Returns:
        AddSourceType indicating whether source is a directory or file.

    Raises:
        FileNotFoundError: If the source path does not exist.
        ValueError: If the source is invalid (directory without plugin.yaml,
            or file that is not .yaml/.yml).
    """
    if not source.exists():
        msg = f"Source path '{source}' does not exist"
        raise FileNotFoundError(msg)

    if source.is_dir():
        # Directory must contain plugin.yaml
        plugin_yaml = source / "plugin.yaml"
        plugin_yml = source / "plugin.yml"
        if not plugin_yaml.exists() and not plugin_yml.exists():
            msg = f"Directory '{source}' does not contain plugin.yaml or plugin.yml"
            raise ValueError(msg)
        return AddSourceType.DIRECTORY

    # File must be .yaml or .yml
    if source.suffix not in (".yaml", ".yml"):
        msg = f"Source file '{source}' must be .yaml or .yml"
        raise ValueError(msg)

    return AddSourceType.FILE


def add_plugin(
    source: str,
    atk_home: Path,
    prompt_func: Callable[[str], str],
) -> str:
    """Add a plugin to ATK Home.

    Args:
        source: Plugin source — local path, registry name, or git URL.
        atk_home: Path to ATK Home directory.
        prompt_func: Function for prompting user input. If the plugin has env vars,
            runs interactive setup before install.

    Returns:
        The sanitized directory name where the plugin was installed.

    Raises:
        ValueError: If ATK Home is not initialized or source is invalid.
        FileNotFoundError: If source does not exist.
        InstallFailedError: If the install lifecycle command fails.
        PluginNotFoundError: If registry plugin name is not found.
        GitSourceError: If git clone or checkout fails.
        GitPluginNotFoundError: If git repo has no .atk/ directory.
    """
    validation = validate_atk_home(atk_home)
    if not validation.is_valid:
        raise ValueError(f"ATK Home '{atk_home}' is not initialized: {', '.join(validation.errors)}")

    resolved = resolve_source(source)

    if resolved.source_type == SourceType.LOCAL:
        if resolved.path is None:
            raise ValueError(f"Source resolved as LOCAL but path is None for '{source}'")
        return _add_local_plugin(resolved.path, atk_home, prompt_func)

    if resolved.source_type == SourceType.REGISTRY:
        if resolved.name is None:
            raise ValueError(f"Source resolved as REGISTRY but name is None for '{source}'")
        return _add_registry_plugin(resolved.name, atk_home, prompt_func)

    if resolved.url is None:
        raise ValueError(f"Source resolved as GIT but url is None for '{source}'")
    return _add_git_plugin(resolved.url, atk_home, prompt_func)


def _check_duplicate(atk_home: Path, directory: str, plugin_name: str) -> None:
    """Raise if a plugin with this directory is already in the manifest."""
    manifest = load_manifest(atk_home)
    if any(p.directory == directory for p in manifest.plugins):
        raise ValueError(f"Plugin '{plugin_name}' is already added (directory: {directory})")


def _check_target_available(target_dir: Path, directory: str) -> None:
    """Raise if the target plugin directory already exists on disk."""
    if target_dir.exists():
        raise ValueError(f"Plugin directory '{directory}' already exists at {target_dir}")


def _add_local_plugin(
    source: Path,
    atk_home: Path,
    prompt_func: Callable[[str], str],
) -> str:
    """Add a plugin from a local path (directory or single file)."""
    source_type = detect_source_type(source)
    schema = load_plugin_schema(source)
    directory = sanitize_directory_name(schema.name)
    _check_duplicate(atk_home, directory, schema.name)

    target_dir = atk_home / "plugins" / directory
    already_in_place = source.resolve() == target_dir.resolve()

    if not already_in_place:
        _check_target_available(target_dir, directory)
        if source_type == AddSourceType.DIRECTORY:
            shutil.copytree(source, target_dir)
        else:
            target_dir.mkdir(parents=True)
            shutil.copy2(source, target_dir / "plugin.yaml")

    source_info = SourceInfo(type=SourceType.LOCAL)
    return _finalize_add(
        schema, atk_home, target_dir, directory, source_info,
        prompt_func, already_in_place, add_gitignore=True,
    )


def _add_registry_plugin(
    name: str,
    atk_home: Path,
    prompt_func: Callable[[str], str],
) -> str:
    """Add a plugin from the registry by name."""
    directory = sanitize_directory_name(name)
    _check_duplicate(atk_home, directory, name)

    target_dir = atk_home / "plugins" / directory
    _check_target_available(target_dir, directory)

    result = fetch_registry_plugin(name=name, target_dir=target_dir)
    schema = load_plugin_schema(target_dir)

    source_info = SourceInfo(type=SourceType.REGISTRY, ref=result.commit_hash)
    return _finalize_add(
        schema,
        atk_home,
        target_dir,
        directory,
        source_info,
        prompt_func,
        already_in_place=False,
        add_gitignore=False,
    )


def _add_git_plugin(
    url: str,
    atk_home: Path,
    prompt_func: Callable[[str], str],
) -> str:
    """Add a plugin from a git repo that follows the .atk/ convention."""
    with tempfile.TemporaryDirectory() as tmp:
        staging_dir = Path(tmp) / "staging"
        result = fetch_git_plugin(url=url, target_dir=staging_dir)
        schema = load_plugin_schema(staging_dir)
        directory = sanitize_directory_name(schema.name)
        _check_duplicate(atk_home, directory, schema.name)

        target_dir = atk_home / "plugins" / directory
        _check_target_available(target_dir, directory)
        shutil.copytree(staging_dir, target_dir)

    source_info = SourceInfo(type=SourceType.GIT, url=url, ref=result.commit_hash)
    return _finalize_add(
        schema,
        atk_home,
        target_dir,
        directory,
        source_info,
        prompt_func,
        already_in_place=False,
        add_gitignore=False,
    )


def _finalize_add(
    schema: PluginSchema,
    atk_home: Path,
    target_dir: Path,
    directory: str,
    source: SourceInfo,
    prompt_func: Callable[[str], str],
    already_in_place: bool,
    add_gitignore: bool,
) -> str:
    """Common post-acquisition workflow for adding a plugin.

    Runs setup, install lifecycle, updates manifest, and commits.
    """
    if schema.env_vars:
        run_setup(schema, target_dir, prompt_func)

    try:
        exit_code = run_lifecycle_command(schema, target_dir, "install")
        if exit_code != 0:
            _cleanup_failed_add(atk_home, target_dir, directory, already_in_place)
            raise InstallFailedError(schema.name, exit_code)
    except LifecycleCommandNotDefinedError:
        pass

    if add_gitignore:
        add_gitignore_exemption(atk_home, directory)

    if source.ref:
        write_atk_ref(target_dir, source.ref)

    auto_commit = _update_manifest(atk_home, schema.name, directory, source=source)

    if auto_commit:
        git_add(atk_home)
        git_commit(atk_home, f"Add plugin '{schema.name}'")

    return directory


def _cleanup_failed_add(atk_home: Path, target_dir: Path, directory: str, already_in_place: bool) -> None:
    """Clean up after a failed add operation.

    Removes the plugin directory and any manifest entry.
    For plugins already in place, leaves the directory intact.

    Args:
        atk_home: Path to ATK Home directory.
        target_dir: Path to the plugin directory to remove.
        directory: Sanitized directory name.
        already_in_place: Whether the plugin was already in the target location.
    """
    # Remove plugin directory only if we copied it
    # If it was already in place, leave it alone
    if not already_in_place and target_dir.exists():
        shutil.rmtree(target_dir)

    # Remove from manifest if it was added
    try:
        manifest = load_manifest(atk_home)
        manifest.plugins = [p for p in manifest.plugins if p.directory != directory]
        save_manifest(manifest, atk_home)
    except Exception:
        # Best effort cleanup - don't fail if manifest update fails
        pass


def _update_manifest(atk_home: Path, plugin_name: str, directory: str, source: SourceInfo) -> bool:
    """Update manifest.yaml with new plugin entry.

    Args:
        atk_home: Path to ATK Home directory.
        plugin_name: Display name of the plugin.
        directory: Sanitized directory name.
        source: Source metadata (type, ref, url).

    Returns:
        True if auto_commit is enabled in config, False otherwise.
    """
    manifest = load_manifest(atk_home)

    # Add new entry (we already checked it doesn't exist in add_plugin)
    manifest.plugins.append(PluginEntry(name=plugin_name, directory=directory, source=source))

    # Write back
    save_manifest(manifest, atk_home)

    return manifest.config.auto_commit
