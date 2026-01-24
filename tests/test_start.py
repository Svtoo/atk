"""Tests for atk start command."""

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
from atk.start import start_all_plugins, start_plugin

runner = CliRunner()


class TestStartPlugin:
    """Tests for start_plugin function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION
        self.plugin_name = "TestPlugin"
        self.plugin_directory = "test-plugin"
        self.plugin_description = "A test plugin"

    def _create_plugin_with_lifecycle(
        self, atk_home: Path, lifecycle: dict[str, str] | None = None
    ) -> Path:
        """Helper to create a plugin with optional lifecycle commands."""
        plugin_dir = atk_home / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml: dict = {
            "schema_version": self.schema_version,
            "name": self.plugin_name,
            "description": self.plugin_description,
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

    def test_runs_start_command(self, tmp_path: Path) -> None:
        """Verify start_plugin runs the start lifecycle command."""
        # Given - plugin with start command that creates a file
        init_atk_home(tmp_path)
        start_command = "touch started.txt"
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"start": start_command}
        )

        # When
        exit_code = start_plugin(tmp_path, self.plugin_directory)

        # Then
        assert exit_code == 0
        assert (plugin_dir / "started.txt").exists()

    def test_raises_when_start_not_defined(self, tmp_path: Path) -> None:
        """Verify start_plugin raises when start command not defined."""
        # Given - plugin without start command
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, {"install": "echo install"})

        # When/Then - should raise exception
        with pytest.raises(
            LifecycleCommandNotDefinedError,
            match="Lifecycle command 'start' not defined",
        ):
            start_plugin(tmp_path, self.plugin_directory)

    def test_raises_when_no_lifecycle_section(self, tmp_path: Path) -> None:
        """Verify start_plugin raises when no lifecycle section."""
        # Given - plugin without lifecycle section
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, None)

        # When/Then - should raise exception
        with pytest.raises(
            LifecycleCommandNotDefinedError,
            match="Lifecycle command 'start' not defined",
        ):
            start_plugin(tmp_path, self.plugin_directory)

    def test_returns_command_exit_code(self, tmp_path: Path) -> None:
        """Verify start_plugin returns the command's exit code."""
        # Given - plugin with start command that exits with code 42
        init_atk_home(tmp_path)
        start_command = "exit 42"
        self._create_plugin_with_lifecycle(tmp_path, {"start": start_command})

        # When
        exit_code = start_plugin(tmp_path, self.plugin_directory)

        # Then
        expected_exit_code = 42
        assert exit_code == expected_exit_code

    def test_raises_when_plugin_not_found(self, tmp_path: Path) -> None:
        """Verify start_plugin raises when plugin not in manifest."""
        # Given - initialized home but no plugin
        init_atk_home(tmp_path)
        nonexistent_plugin = "nonexistent"

        # When/Then
        with pytest.raises(PluginNotFoundError, match=nonexistent_plugin):
            start_plugin(tmp_path, nonexistent_plugin)


class TestStartAll:
    """Tests for start_all_plugins function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION

    def _create_plugin(
        self,
        atk_home: Path,
        name: str,
        directory: str,
        lifecycle: dict[str, str] | None = None,
    ) -> Path:
        """Helper to create a plugin."""
        plugin_dir = atk_home / "plugins" / directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml: dict = {
            "schema_version": self.schema_version,
            "name": name,
            "description": f"Test plugin {name}",
        }
        if lifecycle:
            plugin_yaml["lifecycle"] = lifecycle

        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=name, directory=directory))
        save_manifest(manifest, atk_home)

        return plugin_dir

    def test_start_all_runs_all_plugins(self, tmp_path: Path) -> None:
        """Verify start_all_plugins runs start for all plugins."""
        # Given - two plugins with start commands
        init_atk_home(tmp_path)
        plugin1_dir = self._create_plugin(
            tmp_path, "Plugin1", "plugin-1", {"start": "touch started.txt"}
        )
        plugin2_dir = self._create_plugin(
            tmp_path, "Plugin2", "plugin-2", {"start": "touch started.txt"}
        )

        # When
        result = start_all_plugins(tmp_path)

        # Then
        assert result.succeeded == ["Plugin1", "Plugin2"]
        assert result.failed == []
        assert result.skipped == []
        assert result.all_succeeded is True
        assert (plugin1_dir / "started.txt").exists()
        assert (plugin2_dir / "started.txt").exists()

    def test_start_all_continues_on_failure(self, tmp_path: Path) -> None:
        """Verify start_all_plugins continues after a failure."""
        # Given - first plugin fails, second succeeds
        init_atk_home(tmp_path)
        self._create_plugin(tmp_path, "Plugin1", "plugin-1", {"start": "exit 1"})
        plugin2_dir = self._create_plugin(
            tmp_path, "Plugin2", "plugin-2", {"start": "touch started.txt"}
        )

        # When
        result = start_all_plugins(tmp_path)

        # Then
        assert result.succeeded == ["Plugin2"]
        assert result.failed == [("Plugin1", 1)]
        assert result.skipped == []
        assert result.all_succeeded is False
        assert (plugin2_dir / "started.txt").exists()

    def test_start_all_tracks_skipped_plugins(self, tmp_path: Path) -> None:
        """Verify start_all_plugins tracks plugins without start command."""
        # Given - one plugin with start, one without
        init_atk_home(tmp_path)
        plugin1_dir = self._create_plugin(
            tmp_path, "Plugin1", "plugin-1", {"start": "touch started.txt"}
        )
        self._create_plugin(
            tmp_path, "Plugin2", "plugin-2", {"install": "echo install"}
        )

        # When
        result = start_all_plugins(tmp_path)

        # Then
        assert result.succeeded == ["Plugin1"]
        assert result.failed == []
        assert result.skipped == ["Plugin2"]
        assert result.all_succeeded is True
        assert (plugin1_dir / "started.txt").exists()


class TestStartCli:
    """Tests for atk start CLI command."""

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

    def test_cli_start_single_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI starts a single plugin."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"start": "touch started.txt"}
        )

        # When
        result = runner.invoke(app, ["start", self.plugin_directory])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "Started plugin" in result.output
        assert (plugin_dir / "started.txt").exists()

    def test_cli_start_plugin_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI reports error when plugin not found."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)
        nonexistent_plugin = "nonexistent"

        # When
        result = runner.invoke(app, ["start", nonexistent_plugin])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_start_shows_warning_when_not_defined(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI shows warning when start command not defined."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, {"install": "echo install"})

        # When
        result = runner.invoke(app, ["start", self.plugin_directory])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "no start command defined" in result.output
