"""Tests for atk install command."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.init import init_atk_home
from atk.install import install_plugin
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION

runner = CliRunner()


class TestInstallPlugin:
    """Tests for install_plugin function."""

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

    def test_runs_install_command(self, tmp_path: Path) -> None:
        """Verify install_plugin runs the install lifecycle command."""
        # Given - plugin with install command that creates a file
        init_atk_home(tmp_path)
        install_command = "touch installed.txt"
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"install": install_command}
        )

        # When
        exit_code = install_plugin(tmp_path, self.plugin_directory)

        # Then
        assert exit_code == 0
        assert (plugin_dir / "installed.txt").exists()

    def test_skips_silently_when_install_not_defined(self, tmp_path: Path) -> None:
        """Verify install_plugin returns 0 when install command not defined."""
        # Given - plugin without install command
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, {"start": "echo start"})

        # When
        exit_code = install_plugin(tmp_path, self.plugin_directory)

        # Then - should succeed silently (no-op)
        assert exit_code == 0

    def test_skips_silently_when_no_lifecycle_section(self, tmp_path: Path) -> None:
        """Verify install_plugin returns 0 when no lifecycle section."""
        # Given - plugin without lifecycle section
        init_atk_home(tmp_path)
        self._create_plugin_with_lifecycle(tmp_path, None)

        # When
        exit_code = install_plugin(tmp_path, self.plugin_directory)

        # Then - should succeed silently (no-op)
        assert exit_code == 0

    def test_returns_command_exit_code(self, tmp_path: Path) -> None:
        """Verify install_plugin returns the command's exit code."""
        # Given - plugin with install command that fails
        init_atk_home(tmp_path)
        expected_exit_code = 42
        self._create_plugin_with_lifecycle(
            tmp_path, {"install": f"exit {expected_exit_code}"}
        )

        # When
        exit_code = install_plugin(tmp_path, self.plugin_directory)

        # Then
        assert exit_code == expected_exit_code

    def test_raises_when_plugin_not_found(self, tmp_path: Path) -> None:
        """Verify install_plugin raises when plugin not in manifest."""
        # Given - initialized ATK Home with no plugins
        init_atk_home(tmp_path)
        nonexistent_plugin = "nonexistent"

        # When/Then
        from atk.plugin import PluginNotFoundError

        with pytest.raises(PluginNotFoundError, match=nonexistent_plugin):
            install_plugin(tmp_path, nonexistent_plugin)


class TestInstallCli:
    """Tests for atk install CLI command."""

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

    def test_cli_install_single_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI installs a single plugin."""
        # Given - initialized ATK Home with plugin
        init_atk_home(tmp_path)
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"install": "touch installed.txt"}
        )

        # When
        result = runner.invoke(app, ["install", self.plugin_directory])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "installed.txt").exists()

    def test_cli_install_plugin_not_found(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI returns PLUGIN_NOT_FOUND for unknown plugin."""
        # Given - initialized ATK Home with no plugins
        init_atk_home(tmp_path)
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        nonexistent_plugin = "nonexistent"

        # When
        result = runner.invoke(app, ["install", nonexistent_plugin])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()


class TestInstallAll:
    """Tests for atk install --all functionality."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION

    def _create_plugin(
        self, atk_home: Path, name: str, directory: str, lifecycle: dict[str, str] | None = None
    ) -> Path:
        """Helper to create a plugin with optional lifecycle commands."""
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

    def test_install_all_runs_all_plugins(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify --all installs all plugins in manifest order."""
        # Given - two plugins with install commands
        init_atk_home(tmp_path)
        monkeypatch.setenv("ATK_HOME", str(tmp_path))

        plugin1_dir = self._create_plugin(
            tmp_path, "Plugin1", "plugin-1", {"install": "touch installed1.txt"}
        )
        plugin2_dir = self._create_plugin(
            tmp_path, "Plugin2", "plugin-2", {"install": "touch installed2.txt"}
        )

        # When
        result = runner.invoke(app, ["install", "--all"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin1_dir / "installed1.txt").exists()
        assert (plugin2_dir / "installed2.txt").exists()

    def test_install_all_continues_on_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify --all continues installing after a plugin fails."""
        # Given - first plugin fails, second should still run
        init_atk_home(tmp_path)
        monkeypatch.setenv("ATK_HOME", str(tmp_path))

        self._create_plugin(
            tmp_path, "Plugin1", "plugin-1", {"install": "exit 1"}
        )
        plugin2_dir = self._create_plugin(
            tmp_path, "Plugin2", "plugin-2", {"install": "touch installed2.txt"}
        )

        # When
        result = runner.invoke(app, ["install", "--all"])

        # Then - should report failure but still run second plugin
        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert (plugin2_dir / "installed2.txt").exists()
        assert "failed" in result.output.lower()
