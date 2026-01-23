"""Tests for lifecycle command execution."""

from pathlib import Path

import pytest
import yaml

from atk.init import init_atk_home
from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin import load_plugin
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION


class TestRunLifecycleCommand:
    """Tests for run_lifecycle_command function."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = PLUGIN_SCHEMA_VERSION
        self.plugin_name = "TestPlugin"
        self.plugin_directory = "test-plugin"
        self.plugin_description = "A test plugin"

    def _create_plugin_with_lifecycle(
        self, atk_home: Path, lifecycle: dict[str, str]
    ) -> Path:
        """Helper to create a plugin with lifecycle commands."""
        plugin_dir = atk_home / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml = {
            "schema_version": self.schema_version,
            "name": self.plugin_name,
            "description": self.plugin_description,
            "lifecycle": lifecycle,
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(name=self.plugin_name, directory=self.plugin_directory)
        )
        save_manifest(manifest, atk_home)

        return plugin_dir

    def test_runs_install_command(self, tmp_path: Path) -> None:
        """Verify run_lifecycle_command executes install command."""
        # Given - plugin with install command that creates a file
        init_atk_home(tmp_path)
        install_command = "touch installed.txt"
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"install": install_command}
        )
        plugin, _ = load_plugin(tmp_path, self.plugin_directory)

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == 0
        assert (plugin_dir / "installed.txt").exists()

    def test_runs_command_in_plugin_directory(self, tmp_path: Path) -> None:
        """Verify command runs with plugin directory as cwd."""
        # Given - plugin with command that writes pwd to file
        init_atk_home(tmp_path)
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"install": "pwd > cwd.txt"}
        )
        plugin, _ = load_plugin(tmp_path, self.plugin_directory)

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == 0
        cwd_content = (plugin_dir / "cwd.txt").read_text().strip()
        assert cwd_content == str(plugin_dir)

    def test_returns_command_exit_code(self, tmp_path: Path) -> None:
        """Verify run_lifecycle_command returns command's exit code."""
        # Given - plugin with command that exits with code 42
        init_atk_home(tmp_path)
        exit_code_expected = 42
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"install": f"exit {exit_code_expected}"}
        )
        plugin, _ = load_plugin(tmp_path, self.plugin_directory)

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == exit_code_expected

    def test_raises_when_command_not_defined(self, tmp_path: Path) -> None:
        """Verify raises LifecycleCommandNotDefinedError when command missing."""
        # Given - plugin without start command
        init_atk_home(tmp_path)
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"install": "echo hello"}
        )
        plugin, _ = load_plugin(tmp_path, self.plugin_directory)
        missing_command = "start"

        # When/Then
        with pytest.raises(LifecycleCommandNotDefinedError, match=missing_command):
            run_lifecycle_command(plugin, plugin_dir, missing_command)

    def test_raises_when_lifecycle_section_missing(self, tmp_path: Path) -> None:
        """Verify raises error when plugin has no lifecycle section."""
        # Given - plugin without lifecycle section
        init_atk_home(tmp_path)
        plugin_dir = tmp_path / "plugins" / self.plugin_directory
        plugin_dir.mkdir(parents=True)

        plugin_yaml = {
            "schema_version": self.schema_version,
            "name": self.plugin_name,
            "description": self.plugin_description,
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(tmp_path)
        manifest.plugins.append(
            PluginEntry(name=self.plugin_name, directory=self.plugin_directory)
        )
        save_manifest(manifest, tmp_path)

        plugin, _ = load_plugin(tmp_path, self.plugin_directory)

        # When/Then
        with pytest.raises(LifecycleCommandNotDefinedError, match="install"):
            run_lifecycle_command(plugin, plugin_dir, "install")

    def test_runs_start_command(self, tmp_path: Path) -> None:
        """Verify run_lifecycle_command executes start command."""
        # Given - plugin with start command
        init_atk_home(tmp_path)
        start_command = "touch started.txt"
        plugin_dir = self._create_plugin_with_lifecycle(
            tmp_path, {"start": start_command}
        )
        plugin, _ = load_plugin(tmp_path, self.plugin_directory)

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        assert (plugin_dir / "started.txt").exists()

