"""Tests for plugin loading functionality."""

from pathlib import Path

import pytest
import yaml

from atk.init import init_atk_home
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin import PluginNotFoundError, load_plugin, load_plugin_schema
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, LifecycleConfig, PluginSchema
from tests.conftest import write_plugin_yaml


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
        uninstall_command = "docker compose down -v"
        start_command = "docker compose up -d"

        plugin = PluginSchema(
            schema_version=self.schema_version,
            name=self.plugin_name,
            description=self.plugin_description,
            lifecycle=LifecycleConfig(
                install=install_command,
                uninstall=uninstall_command,
                start=start_command,
            ),
        )
        write_plugin_yaml(plugin_dir, plugin)

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




class TestPluginSchemaOverrides:
    """Tests for custom/overrides.yaml merge behavior in load_plugin_schema."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION
        self.plugin_name = "TestPlugin"
        self.plugin_description = "A test plugin"

    def _create_plugin_dir(self, tmp_path: Path) -> Path:
        """Create a plugin directory with a basic plugin.yaml."""
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir(parents=True)
        plugin = PluginSchema(
            schema_version=self.schema_version,
            name=self.plugin_name,
            description=self.plugin_description,
        )
        write_plugin_yaml(plugin_dir, plugin)
        return plugin_dir

    def test_returns_upstream_schema_when_no_overrides(self, tmp_path: Path) -> None:
        """load_plugin_schema returns upstream plugin.yaml unchanged when no custom/overrides.yaml exists."""
        # Given - a plugin directory with no custom/ directory
        plugin_dir = self._create_plugin_dir(tmp_path)

        # When
        result = load_plugin_schema(plugin_dir)

        # Then - upstream values are returned unchanged
        assert result.name == self.plugin_name
        assert result.description == self.plugin_description
        assert result.lifecycle is None

    def test_merges_lifecycle_override_from_overrides_yaml(self, tmp_path: Path) -> None:
        """load_plugin_schema merges custom/overrides.yaml lifecycle into upstream schema."""
        # Given - plugin with lifecycle, and custom/overrides.yaml overriding start
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir(parents=True)
        upstream_start = "docker compose up -d"
        upstream_stop = "docker compose down"
        plugin = PluginSchema(
            schema_version=self.schema_version,
            name=self.plugin_name,
            description=self.plugin_description,
            lifecycle=LifecycleConfig(start=upstream_start, stop=upstream_stop),
        )
        write_plugin_yaml(plugin_dir, plugin)

        override_start = "./custom/my-start.sh"
        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        overrides = {"lifecycle": {"start": override_start}}
        (custom_dir / "overrides.yaml").write_text(yaml.dump(overrides))

        # When
        result = load_plugin_schema(plugin_dir)

        # Then - start is overridden, stop is preserved from upstream
        assert result.lifecycle is not None
        assert result.lifecycle.start == override_start
        assert result.lifecycle.stop == upstream_stop

    def test_overrides_replace_arrays_entirely(self, tmp_path: Path) -> None:
        """Arrays in overrides.yaml replace upstream arrays (not concatenated)."""
        # Given - plugin with two env vars, override with one different env var
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir(parents=True)
        upstream_var_a = "VAR_A"
        upstream_var_b = "VAR_B"
        plugin = PluginSchema(
            schema_version=self.schema_version,
            name=self.plugin_name,
            description=self.plugin_description,
            env_vars=[
                {"name": upstream_var_a, "required": True},
                {"name": upstream_var_b, "required": False},
            ],
        )
        write_plugin_yaml(plugin_dir, plugin)

        override_var = "CUSTOM_VAR"
        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        overrides = {"env_vars": [{"name": override_var, "required": False}]}
        (custom_dir / "overrides.yaml").write_text(yaml.dump(overrides))

        # When
        result = load_plugin_schema(plugin_dir)

        # Then - env_vars is replaced entirely, not concatenated
        assert len(result.env_vars) == 1
        assert result.env_vars[0].name == override_var

    def test_overrides_add_new_fields(self, tmp_path: Path) -> None:
        """Overrides can add fields that don't exist in upstream plugin.yaml."""
        # Given - plugin with no lifecycle, override adds lifecycle.start
        plugin_dir = self._create_plugin_dir(tmp_path)
        assert load_plugin_schema(plugin_dir).lifecycle is None

        override_start = "./custom/my-start.sh"
        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        overrides = {"lifecycle": {"start": override_start}}
        (custom_dir / "overrides.yaml").write_text(yaml.dump(overrides))

        # When
        result = load_plugin_schema(plugin_dir)

        # Then - lifecycle is added from overrides
        assert result.lifecycle is not None
        assert result.lifecycle.start == override_start

