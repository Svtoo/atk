"""Tests for lifecycle command execution."""

from pathlib import Path
from typing import Callable

import pytest
import yaml

from atk import exit_codes
from atk.cli import app
from atk.lifecycle import (
    LifecycleCommandNotDefinedError,
    restart_all_plugins,
    run_lifecycle_command,
    run_plugin_lifecycle,
)
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin import PluginNotFoundError, load_plugin
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



class TestRestartPlugin:
    """Tests for run_plugin_lifecycle with restart command."""

    def test_runs_restart_command(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify run_plugin_lifecycle runs the restart command from plugin.yaml."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"restart": "touch restarted.txt"})

        exit_code = run_plugin_lifecycle(atk_home, "test-plugin", "restart")

        assert exit_code == 0
        assert (plugin_dir / "restarted.txt").exists()

    def test_raises_when_restart_not_defined(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify run_plugin_lifecycle raises when restart command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start", "stop": "echo stop"})

        with pytest.raises(LifecycleCommandNotDefinedError, match="restart.*not defined"):
            run_plugin_lifecycle(atk_home, "test-plugin", "restart")

    def test_raises_when_plugin_not_found(self, atk_home: Path) -> None:
        """Verify run_plugin_lifecycle raises when plugin not in manifest."""
        with pytest.raises(PluginNotFoundError):
            run_plugin_lifecycle(atk_home, "nonexistent", "restart")

    def test_returns_command_exit_code(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify run_plugin_lifecycle returns the command's exit code."""
        expected_exit_code = 42
        create_plugin("TestPlugin", "test-plugin", {"restart": f"exit {expected_exit_code}"})

        exit_code = run_plugin_lifecycle(atk_home, "test-plugin", "restart")

        assert exit_code == expected_exit_code


class TestRestartAll:
    """Tests for restart_all_plugins function."""

    def test_restart_all_stops_then_starts(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify restart_all_plugins stops all (reverse), then starts all (forward)."""
        order_file = atk_home / "order.txt"
        create_plugin("Plugin1", "plugin1", {
            "stop": f"echo stop1 >> {order_file}",
            "start": f"echo start1 >> {order_file}",
        })
        create_plugin("Plugin2", "plugin2", {
            "stop": f"echo stop2 >> {order_file}",
            "start": f"echo start2 >> {order_file}",
        })

        result = restart_all_plugins(atk_home)

        order = order_file.read_text().strip().split("\n")
        assert order == ["stop2", "stop1", "start1", "start2"]
        assert result.all_succeeded is True

    def test_restart_all_stops_even_when_start_missing(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify restart_all stops plugins even if they have no start command."""
        order_file = atk_home / "order.txt"
        create_plugin("Plugin1", "plugin1", {
            "stop": f"echo stop1 >> {order_file}",
            "start": f"echo start1 >> {order_file}",
        })
        create_plugin("Plugin2", "plugin2", {"stop": f"echo stop2 >> {order_file}"})

        result = restart_all_plugins(atk_home)

        order = order_file.read_text().strip().split("\n")
        assert order == ["stop2", "stop1", "start1"]
        assert "Plugin2" in result.start_skipped

    def test_restart_all_aborts_start_phase_on_stop_failure(self, atk_home: Path, create_plugin: PluginFactory) -> None:
        """Verify restart_all aborts start phase if stop phase has failures."""
        create_plugin("Plugin1", "plugin1", {"stop": "exit 1", "start": "touch started.txt"})

        result = restart_all_plugins(atk_home)

        assert result.all_succeeded is False
        assert len(result.stop_failed) == 1


class TestRestartCli:
    """Tests for atk restart CLI command."""

    def test_cli_restart_single_plugin(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restarts a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"restart": "touch restarted.txt"})

        result = cli_runner.invoke(app, ["restart", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Restarted plugin" in result.output
        assert (plugin_dir / "restarted.txt").exists()

    def test_cli_restart_plugin_not_found(self, atk_home: Path, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        result = cli_runner.invoke(app, ["restart", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_restart_shows_warning_when_not_defined(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when restart command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        result = cli_runner.invoke(app, ["restart", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no restart command defined" in result.output

    def test_cli_restart_all_stops_then_starts(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restart --all stops all then starts all."""
        order_file = atk_home / "order.txt"
        create_plugin("Plugin1", "plugin1", {
            "stop": f"echo stop1 >> {order_file}",
            "start": f"echo start1 >> {order_file}",
        })
        create_plugin("Plugin2", "plugin2", {
            "stop": f"echo stop2 >> {order_file}",
            "start": f"echo start2 >> {order_file}",
        })

        result = cli_runner.invoke(app, ["restart", "--all"])

        assert result.exit_code == exit_codes.SUCCESS
        order = order_file.read_text().strip().split("\n")
        assert order == ["stop2", "stop1", "start1", "start2"]
        assert "Stopped plugin" in result.output
        assert "Started plugin" in result.output

    def test_cli_restart_all_aborts_on_stop_failure(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restart --all aborts start phase if stop fails."""
        create_plugin("Plugin1", "plugin1", {"stop": "exit 1", "start": "touch started.txt"})

        result = cli_runner.invoke(app, ["restart", "--all"])

        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert "stop phase had failures" in result.output
        assert "Started plugin" not in result.output