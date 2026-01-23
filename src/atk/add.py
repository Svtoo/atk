"""Plugin add functionality for ATK.

Handles adding plugins from local directories or single YAML files.
"""

import shutil
from enum import Enum
from pathlib import Path

import yaml
from pydantic import ValidationError

from atk.errors import format_validation_errors
from atk.git import git_add, git_commit
from atk.home import validate_atk_home
from atk.manifest_schema import ManifestSchema, PluginEntry
from atk.plugin_schema import PluginSchema
from atk.sanitize import sanitize_directory_name


class SourceType(str, Enum):
    """Type of plugin source."""

    DIRECTORY = "directory"
    FILE = "file"


def detect_source_type(source: Path) -> SourceType:
    """Detect whether the source is a directory or single file.

    Args:
        source: Path to the plugin source (directory or file).

    Returns:
        SourceType indicating whether source is a directory or file.

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
        return SourceType.DIRECTORY

    # File must be .yaml or .yml
    if source.suffix not in (".yaml", ".yml"):
        msg = f"Source file '{source}' must be .yaml or .yml"
        raise ValueError(msg)

    return SourceType.FILE


def load_plugin_schema(source: Path) -> PluginSchema:
    """Load and validate plugin.yaml from source.

    Args:
        source: Path to plugin directory or single plugin.yaml file.

    Returns:
        Validated PluginSchema instance.

    Raises:
        FileNotFoundError: If source or plugin.yaml does not exist.
        ValueError: If YAML is invalid or schema validation fails.
    """
    if not source.exists():
        msg = f"Source path '{source}' does not exist"
        raise FileNotFoundError(msg)

    # Determine the actual plugin.yaml path
    if source.is_dir():
        plugin_yaml = source / "plugin.yaml"
        if not plugin_yaml.exists():
            plugin_yaml = source / "plugin.yml"
        if not plugin_yaml.exists():
            msg = f"Directory '{source}' does not contain plugin.yaml or plugin.yml"
            raise FileNotFoundError(msg)
    else:
        plugin_yaml = source

    # Parse YAML
    try:
        content = plugin_yaml.read_text()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in '{plugin_yaml}': {e}"
        raise ValueError(msg) from e

    if data is None:
        msg = f"Invalid YAML in '{plugin_yaml}': empty file"
        raise ValueError(msg)

    # Validate against schema
    try:
        return PluginSchema.model_validate(data)
    except ValidationError as e:
        clean_errors = format_validation_errors(e)
        msg = f"Invalid plugin '{plugin_yaml}': {clean_errors}"
        raise ValueError(msg) from e


def add_plugin(source: Path, atk_home: Path) -> str:
    """Add a plugin to ATK Home.

    Args:
        source: Path to plugin source (directory or single file).
        atk_home: Path to ATK Home directory.

    Returns:
        The sanitized directory name where the plugin was installed.

    Raises:
        ValueError: If ATK Home is not initialized or source is invalid.
        FileNotFoundError: If source does not exist.
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

    # Determine target directory
    target_dir = atk_home / "plugins" / directory

    # Error if plugin already exists
    if target_dir.exists():
        msg = f"Plugin directory '{directory}' already exists at {target_dir}"
        raise ValueError(msg)

    # Copy files based on source type
    if source_type == SourceType.DIRECTORY:
        shutil.copytree(source, target_dir)
    else:
        # Single file: create directory and copy just the yaml
        target_dir.mkdir(parents=True)
        shutil.copy2(source, target_dir / "plugin.yaml")

    # Update manifest and get auto_commit setting
    auto_commit = _update_manifest(atk_home, schema.name, directory)

    # Commit changes if auto_commit is enabled
    if auto_commit:
        git_add(atk_home)
        git_commit(atk_home, f"Add plugin '{schema.name}'")

    return directory


def _update_manifest(atk_home: Path, plugin_name: str, directory: str) -> bool:
    """Update manifest.yaml with new plugin entry.

    Args:
        atk_home: Path to ATK Home directory.
        plugin_name: Display name of the plugin.
        directory: Sanitized directory name.

    Returns:
        True if auto_commit is enabled in config, False otherwise.
    """
    manifest_path = atk_home / "manifest.yaml"
    content = manifest_path.read_text()
    data = yaml.safe_load(content)
    manifest = ManifestSchema.model_validate(data)

    # Remove existing entry with same directory (if any)
    manifest.plugins = [p for p in manifest.plugins if p.directory != directory]

    # Add new entry
    manifest.plugins.append(PluginEntry(name=plugin_name, directory=directory))

    # Write back
    manifest_path.write_text(
        yaml.dump(manifest.model_dump(), default_flow_style=False, sort_keys=False)
    )

    return manifest.config.auto_commit
