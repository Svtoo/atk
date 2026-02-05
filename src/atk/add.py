"""Plugin add functionality for ATK.

Handles adding plugins from local directories or single YAML files.
"""

import shutil
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from atk.git import add_gitignore_exemption, git_add, git_commit
from atk.home import validate_atk_home
from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import PluginEntry, SourceType, load_manifest, save_manifest
from atk.plugin import load_plugin_schema
from atk.sanitize import sanitize_directory_name
from atk.setup import run_setup


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
    source: Path,
    atk_home: Path,
    prompt_func: Callable[[str], str],
) -> str:
    """Add a plugin to ATK Home.

    Args:
        source: Path to plugin source (directory or single file).
        atk_home: Path to ATK Home directory.
        prompt_func: Function for prompting user input. If the plugin has env vars,
            runs interactive setup before install.

    Returns:
        The sanitized directory name where the plugin was installed.

    Raises:
        ValueError: If ATK Home is not initialized or source is invalid.
        FileNotFoundError: If source does not exist.
        InstallFailedError: If the install lifecycle command fails.
    """
    # Validate ATK Home is initialized
    validation = validate_atk_home(atk_home)
    if not validation.is_valid:
        msg = f"ATK Home '{atk_home}' is not initialized: {', '.join(validation.errors)}"
        raise ValueError(msg)

    # Detect source type and load schema
    source_type = detect_source_type(source)
    schema = load_plugin_schema(source)

    # Generate directory name from plugin name
    directory = sanitize_directory_name(schema.name)

    # Fail fast: check if plugin is already in manifest
    manifest = load_manifest(atk_home)
    if any(p.directory == directory for p in manifest.plugins):
        msg = f"Plugin '{schema.name}' is already added (directory: {directory})"
        raise ValueError(msg)

    # Determine target directory
    target_dir = atk_home / "plugins" / directory

    # Check if source is already in the target location (plugin created directly in plugins/)
    source_resolved = source.resolve()
    target_resolved = target_dir.resolve()
    already_in_place = source_resolved == target_resolved

    if not already_in_place:
        # Check for directory conflict (different source, same target name)
        if target_dir.exists():
            msg = f"Plugin directory '{directory}' already exists at {target_dir}"
            raise ValueError(msg)

        # Copy files to plugins/ directory
        if source_type == AddSourceType.DIRECTORY:
            shutil.copytree(source, target_dir)
        else:
            # Single file: create directory and copy just the yaml
            target_dir.mkdir(parents=True)
            shutil.copy2(source, target_dir / "plugin.yaml")

    # Run interactive setup if plugin has env vars
    if schema.env_vars:
        run_setup(schema, target_dir, prompt_func)

    # Run install lifecycle command if defined
    # Skip silently if not defined (unlike standalone atk install which warns)
    try:
        exit_code = run_lifecycle_command(schema, target_dir, "install")
        if exit_code != 0:
            # Clean up on failure
            _cleanup_failed_add(atk_home, target_dir, directory, already_in_place)
            raise InstallFailedError(schema.name, exit_code)
    except LifecycleCommandNotDefinedError:
        # Skip silently - install is optional
        pass

    # Add gitignore exemption for ALL local plugins
    add_gitignore_exemption(atk_home, directory)

    # Update manifest and get auto_commit setting
    # All local plugins get source=LOCAL
    auto_commit = _update_manifest(atk_home, schema.name, directory, source=SourceType.LOCAL)

    # Commit changes if auto_commit is enabled
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


def _update_manifest(atk_home: Path, plugin_name: str, directory: str, source: SourceType) -> bool:
    """Update manifest.yaml with new plugin entry.

    Args:
        atk_home: Path to ATK Home directory.
        plugin_name: Display name of the plugin.
        directory: Sanitized directory name.
        source: Source type (LOCAL, REGISTRY, or GIT).

    Returns:
        True if auto_commit is enabled in config, False otherwise.
    """
    manifest = load_manifest(atk_home)

    # Add new entry (we already checked it doesn't exist in add_plugin)
    manifest.plugins.append(PluginEntry(name=plugin_name, directory=directory, source=source))

    # Write back
    save_manifest(manifest, atk_home)

    return manifest.config.auto_commit
