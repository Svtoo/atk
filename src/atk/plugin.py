"""Plugin loading functionality for ATK.

Handles loading plugins from ATK Home by name or directory.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from atk.errors import format_validation_errors
from atk.manifest_schema import load_manifest
from atk.plugin_schema import PluginSchema


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

    # Load plugin.yaml from plugin directory
    plugin_dir = atk_home / "plugins" / plugin_entry.directory
    plugin_yaml_path = plugin_dir / "plugin.yaml"

    if not plugin_yaml_path.exists():
        # Try .yml extension
        plugin_yaml_path = plugin_dir / "plugin.yml"
        if not plugin_yaml_path.exists():
            msg = f"plugin.yaml not found at {plugin_dir}"
            raise FileNotFoundError(msg)

    # Parse and validate
    try:
        content = plugin_yaml_path.read_text()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        msg = f"Invalid YAML in '{plugin_yaml_path}': {e}"
        raise ValueError(msg) from e

    if data is None:
        msg = f"Invalid YAML in '{plugin_yaml_path}': empty file"
        raise ValueError(msg)

    try:
        schema = PluginSchema.model_validate(data)
    except ValidationError as e:
        clean_errors = format_validation_errors(e)
        msg = f"Invalid plugin '{plugin_yaml_path}': {clean_errors}"
        raise ValueError(msg) from e

    return schema, plugin_dir

