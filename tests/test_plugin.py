"""Tests for plugin loading functionality."""

from pathlib import Path

import pytest
import yaml

from atk.init import init_atk_home
from atk.manifest_schema import (
    ManifestSchema,
    PluginEntry,
    load_manifest,
    save_manifest,
)
from atk.plugin import PluginNotFoundError, load_plugin
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, PluginSchema


class TestLoadPlugin:
    """Tests for load_plugin function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION
        self.plugin_name = "OpenMemory"
        self.plugin_directory = "openmemory"
        self.plugin_description = "A test plugin"

    def _create_plugin(self, atk_home: Path, name: str, directory: str) -> Path:
        """Helper to create a plugin in ATK Home."""
        plugin_dir = atk_home / "plugins" / directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml = {
            "schema_version": self.schema_version,
            "name": name,
            "description": self.plugin_description,
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        # Add to manifest
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=name, directory=directory))
        save_manifest(manifest, atk_home)

        return plugin_dir

    def test_loads_plugin_by_directory(self, tmp_path: Path) -> None:
        """Verify load_plugin finds plugin by directory name."""
        # Given - initialized ATK Home with a plugin
        init_atk_home(tmp_path)
        self._create_plugin(tmp_path, self.plugin_name, self.plugin_directory)

        # When
        result, plugin_dir = load_plugin(tmp_path, self.plugin_directory)

        # Then
        assert isinstance(result, PluginSchema)
        assert result.name == self.plugin_name
        assert result.description == self.plugin_description

    def test_loads_plugin_by_name(self, tmp_path: Path) -> None:
        """Verify load_plugin finds plugin by display name."""
        # Given - initialized ATK Home with a plugin
        init_atk_home(tmp_path)
        self._create_plugin(tmp_path, self.plugin_name, self.plugin_directory)

        # When
        result, plugin_dir = load_plugin(tmp_path, self.plugin_name)

        # Then
        assert isinstance(result, PluginSchema)
        assert result.name == self.plugin_name

    def test_raises_when_plugin_not_found(self, tmp_path: Path) -> None:
        """Verify load_plugin raises PluginNotFoundError for unknown plugin."""
        # Given - initialized ATK Home with no plugins
        init_atk_home(tmp_path)
        unknown_plugin = "nonexistent-plugin"

        # When/Then
        with pytest.raises(PluginNotFoundError, match=unknown_plugin):
            load_plugin(tmp_path, unknown_plugin)

    def test_raises_when_plugin_yaml_missing(self, tmp_path: Path) -> None:
        """Verify load_plugin raises error when plugin.yaml is missing."""
        # Given - plugin in manifest but no plugin.yaml file
        init_atk_home(tmp_path)
        plugin_dir = tmp_path / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True)

        manifest = load_manifest(tmp_path)
        manifest.plugins.append(
            PluginEntry(name=self.plugin_name, directory=self.plugin_directory)
        )
        save_manifest(manifest, tmp_path)

        # When/Then
        with pytest.raises(FileNotFoundError, match="plugin.yaml"):
            load_plugin(tmp_path, self.plugin_directory)

    def test_loads_plugin_with_lifecycle_commands(self, tmp_path: Path) -> None:
        """Verify load_plugin loads lifecycle configuration."""
        # Given - plugin with lifecycle commands
        init_atk_home(tmp_path)
        plugin_dir = tmp_path / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True)

        install_command = "docker compose pull"
        start_command = "docker compose up -d"
        plugin_yaml = {
            "schema_version": self.schema_version,
            "name": self.plugin_name,
            "description": self.plugin_description,
            "lifecycle": {
                "install": install_command,
                "start": start_command,
            },
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(tmp_path)
        manifest.plugins.append(
            PluginEntry(name=self.plugin_name, directory=self.plugin_directory)
        )
        save_manifest(manifest, tmp_path)

        # When
        result, plugin_dir = load_plugin(tmp_path, self.plugin_directory)

        # Then
        assert result.lifecycle is not None
        assert result.lifecycle.install == install_command
        assert result.lifecycle.start == start_command

    def test_returns_plugin_directory_path(self, tmp_path: Path) -> None:
        """Verify load_plugin returns plugin with directory path."""
        # Given - initialized ATK Home with a plugin
        init_atk_home(tmp_path)
        plugin_dir = self._create_plugin(
            tmp_path, self.plugin_name, self.plugin_directory
        )

        # When
        result, result_dir = load_plugin(tmp_path, self.plugin_directory)

        # Then
        assert result_dir == plugin_dir

