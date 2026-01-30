"""Shared test fixtures for ATK tests."""

from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk.init import init_atk_home
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin_schema import (
    PLUGIN_SCHEMA_VERSION,
    EnvVarConfig,
    LifecycleConfig,
    McpConfig,
    PluginSchema,
    PortConfig,
)


def serialize_plugin(plugin: PluginSchema) -> str:
    """Serialize a PluginSchema to YAML string.

    Helper function for tests that need to write plugin.yaml files manually.
    """
    return yaml.dump(plugin.model_dump(exclude_none=True), default_flow_style=False)


def write_plugin_yaml(path: Path, plugin: PluginSchema) -> None:
    """Write a PluginSchema to a plugin.yaml file.

    Combines serialization and file writing in one operation.

    Args:
        path: Path to the plugin.yaml file (or directory containing it)
        plugin: PluginSchema instance to serialize and write
    """
    # If path is a directory, append plugin.yaml
    if path.is_dir():
        path = path / "plugin.yaml"
    path.write_text(serialize_plugin(plugin))


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def atk_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create and initialize an ATK home directory.

    Sets ATK_HOME environment variable and initializes the directory structure.
    Returns the path to the ATK home directory.
    """
    monkeypatch.setenv("ATK_HOME", str(tmp_path))
    init_atk_home(tmp_path)
    return tmp_path


# Type alias for the plugin factory function
PluginFactory = Callable[..., Path]


@pytest.fixture
def create_plugin(atk_home: Path) -> PluginFactory:
    """Factory fixture that returns a function to create plugins.

    Supports two calling patterns:

    1. New pattern (preferred) - Pass a PluginSchema instance:
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="MyPlugin",
            description="Test plugin",
            lifecycle=LifecycleConfig(start="echo hi"),
        )
        plugin_dir = create_plugin(plugin=plugin, directory="my-plugin")

    2. Legacy pattern (backward compatible) - Pass individual parameters:
        plugin_dir = create_plugin(
            "MyPlugin",
            "my-plugin",
            lifecycle=LifecycleConfig(start="echo hi"),
        )

    The directory parameter is required in both patterns.
    """

    def _create(
        name: str | None = None,
        directory: str | None = None,
        lifecycle: LifecycleConfig | dict | None = None,
        ports: list[PortConfig] | None = None,
        env_vars: list[EnvVarConfig] | None = None,
        mcp: McpConfig | None = None,
        *,
        plugin: PluginSchema | None = None,
    ) -> Path:
        # New pattern: plugin instance provided
        if plugin is not None:
            if directory is None:
                msg = "directory parameter is required when using plugin parameter"
                raise ValueError(msg)
            final_plugin = plugin
            final_directory = directory
        # Legacy pattern: individual parameters
        else:
            if name is None or directory is None:
                msg = "name and directory are required when not using plugin parameter"
                raise ValueError(msg)
            # Convert dict to LifecycleConfig if needed (for backward compatibility)
            if isinstance(lifecycle, dict):
                lifecycle = LifecycleConfig.model_validate(lifecycle)
            final_plugin = PluginSchema(
                schema_version=PLUGIN_SCHEMA_VERSION,
                name=name,
                description=f"Test plugin {name}",
                lifecycle=lifecycle,
                ports=ports or [],
                env_vars=env_vars or [],
                mcp=mcp,
            )
            final_directory = directory

        plugin_dir = atk_home / "plugins" / final_directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        (plugin_dir / "plugin.yaml").write_text(
            yaml.dump(final_plugin.model_dump(exclude_none=True))
        )

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(name=final_plugin.name, directory=final_directory)
        )
        save_manifest(manifest, atk_home)

        return plugin_dir

    return _create

