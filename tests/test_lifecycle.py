"""Tests for lifecycle command execution."""

from pathlib import Path
from typing import Callable

import pytest
import yaml

from atk import exit_codes
from atk.cli import app
from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin import load_plugin
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION

# Type alias for the plugin factory fixture
PluginFactory = Callable[[str, str, dict[str, str] | None], Path]


class TestRunLifecycleCommand:
    """Tests for run_lifecycle_command function."""

    def test_runs_install_command(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify run_lifecycle_command executes install command."""
        # Given
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "touch installed.txt"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == 0
        assert (plugin_dir / "installed.txt").exists()

    def test_runs_command_in_plugin_directory(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify command runs with plugin directory as cwd."""
        # Given
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "pwd > cwd.txt"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == 0
        cwd_content = (plugin_dir / "cwd.txt").read_text().strip()
        assert cwd_content == str(plugin_dir)

    def test_returns_command_exit_code(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify run_lifecycle_command returns command's exit code."""
        # Given
        expected_exit_code = 42
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": f"exit {expected_exit_code}"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == expected_exit_code

    def test_raises_when_command_not_defined(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify raises LifecycleCommandNotDefinedError when command missing."""
        # Given
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "echo hello"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When/Then
        with pytest.raises(LifecycleCommandNotDefinedError, match="start"):
            run_lifecycle_command(plugin, plugin_dir, "start")

    def test_raises_when_lifecycle_section_missing(self, atk_home: Path) -> None:
        """Verify raises error when plugin has no lifecycle section."""
        # Given - plugin without lifecycle section (manual creation)
        plugin_dir = atk_home / "plugins" / "test-plugin"
        plugin_dir.mkdir(parents=True)

        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": "TestPlugin",
            "description": "A test plugin",
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name="TestPlugin", directory="test-plugin"))
        save_manifest(manifest, atk_home)

        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When/Then
        with pytest.raises(LifecycleCommandNotDefinedError, match="install"):
            run_lifecycle_command(plugin, plugin_dir, "install")

    def test_runs_start_command(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify run_lifecycle_command executes start command."""
        # Given
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"start": "touch started.txt"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        assert (plugin_dir / "started.txt").exists()



# =============================================================================
# CLI Tests for Lifecycle Commands
# =============================================================================


class TestStartCli:
    """Tests for atk start CLI command."""

    def test_cli_start_single_plugin(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI starts a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"start": "touch started.txt"})

        result = cli_runner.invoke(app, ["start", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Started plugin" in result.output
        assert (plugin_dir / "started.txt").exists()

    def test_cli_start_plugin_not_found(self, atk_home: Path, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        result = cli_runner.invoke(app, ["start", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_start_shows_warning_when_not_defined(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when start command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        result = cli_runner.invoke(app, ["start", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no start command defined" in result.output


class TestStopCli:
    """Tests for atk stop CLI command."""

    def test_cli_stop_single_plugin(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI stops a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"stop": "touch stopped.txt"})

        result = cli_runner.invoke(app, ["stop", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Stopped plugin" in result.output
        assert (plugin_dir / "stopped.txt").exists()

    def test_cli_stop_plugin_not_found(self, atk_home: Path, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        result = cli_runner.invoke(app, ["stop", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_stop_shows_warning_when_not_defined(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when stop command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        result = cli_runner.invoke(app, ["stop", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no stop command defined" in result.output


class TestInstallCli:
    """Tests for atk install CLI command."""

    def test_cli_install_single_plugin(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI installs a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "touch installed.txt"})

        result = cli_runner.invoke(app, ["install", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "installed.txt").exists()

    def test_cli_install_plugin_not_found(self, atk_home: Path, cli_runner) -> None:
        """Verify CLI returns PLUGIN_NOT_FOUND for unknown plugin."""
        result = cli_runner.invoke(app, ["install", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_install_all_runs_all_plugins(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify --all installs all plugins in manifest order."""
        plugin1_dir = create_plugin("Plugin1", "plugin-1", {"install": "touch installed1.txt"})
        plugin2_dir = create_plugin("Plugin2", "plugin-2", {"install": "touch installed2.txt"})

        result = cli_runner.invoke(app, ["install", "--all"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin1_dir / "installed1.txt").exists()
        assert (plugin2_dir / "installed2.txt").exists()

    def test_install_all_continues_on_failure(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify --all continues installing after a plugin fails."""
        create_plugin("Plugin1", "plugin-1", {"install": "exit 1"})
        plugin2_dir = create_plugin("Plugin2", "plugin-2", {"install": "touch installed2.txt"})

        result = cli_runner.invoke(app, ["install", "--all"])

        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert (plugin2_dir / "installed2.txt").exists()
        assert "failed" in result.output.lower()