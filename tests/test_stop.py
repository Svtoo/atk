"""Tests for atk stop command."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.init import init_atk_home
from atk.lifecycle import LifecycleCommandNotDefinedError
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin import PluginNotFoundError
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION
from atk.stop import stop_all_plugins, stop_plugin

runner = CliRunner()


class TestStopPlugin:
    """Tests for stop_plugin function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION
        self.plugin_name = "TestPlugin"
        self.plugin_directory = "test-plugin"

    def _create_plugin_with_lifecycle(
        self, atk_home: Path, lifecycle: dict[str, str] | None = None
    ) -> Path:
        """Helper to create a plugin with optional lifecycle commands."""
        plugin_dir = atk_home / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml: dict = {
            "schema_version": self.schema_version,
            "name": self.plugin_name,
            "description": "A test plugin",
        }
        if lifecycle:
            plugin_yaml["lifecycle"] = lifecycle

        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(name=self.plugin_name, directory=self.plugin_directory)
        )
        save_manifest(manifest, atk_home)

        return plugin_dir

    def test_runs_stop_command(self, tmp_path: Path) -> None:
        """Verify stop_plugin runs the stop command from plugin.yaml."""
        # Given
        init_atk_home(tmp_path)
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"stop": "touch stopped.txt"}
        )

        # When
        exit_code = stop_plugin(tmp_path, self.plugin_directory)

        # Then
        assert exit_code == 0
        assert (plugin_dir / "stopped.txt").exists()

    def test_raises_when_stop_not_defined(self, tmp_path: Path) -> None:
        """Verify stop_plugin raises when stop command not defined."""
        # Given
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, {"install": "echo install"})

        # When/Then
        with pytest.raises(
            LifecycleCommandNotDefinedError, match="stop.*not defined"
        ):
            stop_plugin(tmp_path, self.plugin_directory)

    def test_raises_when_plugin_not_found(self, tmp_path: Path) -> None:
        """Verify stop_plugin raises when plugin not in manifest."""
        # Given
        init_atk_home(tmp_path)
        nonexistent_plugin = "nonexistent"

        # When/Then
        with pytest.raises(PluginNotFoundError):
            stop_plugin(tmp_path, nonexistent_plugin)


class TestStopAll:
    """Tests for stop_all_plugins function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION

    def _create_plugin(
        self, atk_home: Path, name: str, directory: str, lifecycle: dict[str, str] | None = None
    ) -> Path:
        """Helper to create a plugin."""
        plugin_dir = atk_home / "plugins" / directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml: dict = {
            "schema_version": self.schema_version,
            "name": name,
            "description": f"Plugin {name}",
        }
        if lifecycle:
            plugin_yaml["lifecycle"] = lifecycle

        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=name, directory=directory))
        save_manifest(manifest, atk_home)

        return plugin_dir

    def test_stop_all_runs_in_reverse_order(self, tmp_path: Path) -> None:
        """Verify stop_all_plugins stops in REVERSE manifest order."""
        # Given
        init_atk_home(tmp_path)
        # Create plugins in order: Plugin1, Plugin2, Plugin3
        self._create_plugin(
            tmp_path, "Plugin1", "plugin1", {"stop": "touch stopped.txt"}
        )
        self._create_plugin(
            tmp_path, "Plugin2", "plugin2", {"stop": "touch stopped.txt"}
        )
        self._create_plugin(
            tmp_path, "Plugin3", "plugin3", {"stop": "touch stopped.txt"}
        )

        # When
        result = stop_all_plugins(tmp_path)

        # Then - succeeded list should be in reverse order: 3, 2, 1
        assert result.succeeded == ["Plugin3", "Plugin2", "Plugin1"]
        assert result.all_succeeded is True

    def test_stop_all_tracks_skipped_plugins(self, tmp_path: Path) -> None:
        """Verify stop_all_plugins tracks plugins without stop command."""
        # Given
        init_atk_home(tmp_path)
        plugin1_dir = self._create_plugin(
            tmp_path, "Plugin1", "plugin1", {"stop": "touch stopped.txt"}
        )
        # Plugin2 has no stop command
        self._create_plugin(
            tmp_path, "Plugin2", "plugin2", {"install": "echo install"}
        )

        # When
        result = stop_all_plugins(tmp_path)

        # Then - reverse order, Plugin2 first but skipped
        assert result.succeeded == ["Plugin1"]
        assert result.skipped == ["Plugin2"]
        assert result.all_succeeded is True
        assert (plugin1_dir / "stopped.txt").exists()


class TestStopCli:
    """Tests for atk stop CLI command."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION
        self.plugin_name = "TestPlugin"
        self.plugin_directory = "test-plugin"

    def _create_plugin_with_lifecycle(
        self, atk_home: Path, lifecycle: dict[str, str] | None = None
    ) -> Path:
        """Helper to create a plugin with optional lifecycle commands."""
        plugin_dir = atk_home / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml: dict = {
            "schema_version": self.schema_version,
            "name": self.plugin_name,
            "description": "A test plugin",
        }
        if lifecycle:
            plugin_yaml["lifecycle"] = lifecycle

        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(name=self.plugin_name, directory=self.plugin_directory)
        )
        save_manifest(manifest, atk_home)

        return plugin_dir

    def test_cli_stop_single_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI stops a single plugin."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"stop": "touch stopped.txt"}
        )

        # When
        result = runner.invoke(app, ["stop", self.plugin_directory])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "Stopped plugin" in result.output
        assert (plugin_dir / "stopped.txt").exists()

    def test_cli_stop_plugin_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI reports error when plugin not found."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)
        nonexistent_plugin = "nonexistent"

        # When
        result = runner.invoke(app, ["stop", nonexistent_plugin])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_stop_shows_warning_when_not_defined(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI shows warning when stop command not defined."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, {"install": "echo install"})

        # When
        result = runner.invoke(app, ["stop", self.plugin_directory])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "no stop command defined" in result.output
