"""Plugin loading functionality for ATK.

Handles loading plugins from ATK Home by name or directory.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from atk.errors import format_validation_errors
from atk.manifest_schema import load_manifest
from atk.plugin_schema import PluginSchema


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


class PluginNotFoundError(Exception):
    """Raised when a plugin is not found in the manifest."""

    def __init__(self, identifier: str) -> None:
        """Initialize with the plugin identifier that was not found."""
        self.identifier = identifier
        super().__init__(f"Plugin '{identifier}' not found in manifest")


def load_plugin(atk_home: Path, identifier: str) -> tuple[PluginSchema, Path]:
    """Load a plugin by name or directory.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory to find.

    Returns:
        Tuple of (PluginSchema, plugin_directory_path).

    Raises:
        PluginNotFoundError: If plugin is not in the manifest.
        FileNotFoundError: If plugin.yaml does not exist.
        ValueError: If plugin.yaml is invalid.
    """
    # Load manifest and find plugin
    manifest = load_manifest(atk_home)

    plugin_entry = next(
        (p for p in manifest.plugins if p.directory == identifier or p.name == identifier),
        None,
    )

    if plugin_entry is None:
        raise PluginNotFoundError(identifier)

    plugin_dir = atk_home / "plugins" / plugin_entry.directory
    schema = load_plugin_schema(plugin_dir)
    return schema, plugin_dir

