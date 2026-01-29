"""Tests for lifecycle command execution."""

from collections.abc import Callable
from pathlib import Path

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

    def test_injects_env_vars_from_env_file(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify run_lifecycle_command injects env vars from .env file."""
        # Given
        env_var_name = "MY_TEST_VAR"
        env_var_value = "test_value_123"
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {"start": f"echo ${env_var_name} > env_output.txt"},
        )
        env_file = plugin_dir / ".env"
        env_file.write_text(f"{env_var_name}={env_var_value}\n")
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        output_file = plugin_dir / "env_output.txt"
        assert output_file.exists()
        assert output_file.read_text().strip() == env_var_value

    def test_env_file_vars_override_system_env(
        self, atk_home: Path, create_plugin: PluginFactory, monkeypatch
    ) -> None:
        """Verify .env file vars take precedence over system environment."""
        # Given
        env_var_name = "OVERRIDE_TEST_VAR"
        system_value = "from_system"
        file_value = "from_file"
        monkeypatch.setenv(env_var_name, system_value)
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {"start": f"echo ${env_var_name} > env_output.txt"},
        )
        env_file = plugin_dir / ".env"
        env_file.write_text(f"{env_var_name}={file_value}\n")
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        output_file = plugin_dir / "env_output.txt"
        assert output_file.read_text().strip() == file_value

    def test_system_env_available_when_no_env_file(
        self, atk_home: Path, create_plugin: PluginFactory, monkeypatch
    ) -> None:
        """Verify system environment is available when no .env file exists."""
        # Given
        env_var_name = "SYSTEM_ONLY_VAR"
        env_var_value = "system_value"
        monkeypatch.setenv(env_var_name, env_var_value)
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {"start": f"echo ${env_var_name} > env_output.txt"},
        )
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        output_file = plugin_dir / "env_output.txt"
        assert output_file.read_text().strip() == env_var_value


# =============================================================================
# CLI Tests for Lifecycle Commands
# =============================================================================


@pytest.mark.usefixtures("atk_home")
class TestStartCli:
    """Tests for atk start CLI command."""

    def test_cli_start_single_plugin(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI starts a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"start": "touch started.txt"})

        result = cli_runner.invoke(app, ["start", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Started plugin" in result.output
        assert (plugin_dir / "started.txt").exists()

    def test_cli_start_plugin_not_found(self, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        result = cli_runner.invoke(app, ["start", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_start_shows_warning_when_not_defined(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when start command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        result = cli_runner.invoke(app, ["start", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no start command defined" in result.output

    def test_cli_start_fails_with_missing_required_env_vars(
        self, atk_home: Path, cli_runner
    ) -> None:
        """Verify CLI fails with exit code 8 when required env vars are missing."""
        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        required_var = "REQUIRED_API_KEY"
        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": plugin_name,
            "description": "Test plugin",
            "lifecycle": {"start": "echo starting"},
            "env_vars": [{"name": required_var, "required": True}],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["start", plugin_dir_name])

        assert result.exit_code == exit_codes.ENV_NOT_CONFIGURED
        assert required_var in result.output
        assert "Missing required" in result.output

    def test_cli_start_succeeds_when_required_env_var_in_env_file(
        self, atk_home: Path, cli_runner
    ) -> None:
        """Verify CLI succeeds when required env var is set in .env file."""
        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        required_var = "REQUIRED_API_KEY"
        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": plugin_name,
            "description": "Test plugin",
            "lifecycle": {"start": "echo starting"},
            "env_vars": [{"name": required_var, "required": True}],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
        (plugin_dir / ".env").write_text(f"{required_var}=secret_value\n")
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["start", plugin_dir_name])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Started plugin" in result.output

    def test_cli_start_succeeds_when_required_env_var_in_system_env(
        self, atk_home: Path, cli_runner, monkeypatch
    ) -> None:
        """Verify CLI succeeds when required env var is set in system environment."""
        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        required_var = "REQUIRED_API_KEY"
        monkeypatch.setenv(required_var, "system_value")
        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": plugin_name,
            "description": "Test plugin",
            "lifecycle": {"start": "echo starting"},
            "env_vars": [{"name": required_var, "required": True}],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["start", plugin_dir_name])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Started plugin" in result.output


@pytest.mark.usefixtures("atk_home")
class TestStopCli:
    """Tests for atk stop CLI command."""

    def test_cli_stop_single_plugin(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI stops a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"stop": "touch stopped.txt"})

        result = cli_runner.invoke(app, ["stop", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Stopped plugin" in result.output
        assert (plugin_dir / "stopped.txt").exists()

    def test_cli_stop_plugin_not_found(self, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        result = cli_runner.invoke(app, ["stop", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_stop_shows_warning_when_not_defined(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when stop command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        result = cli_runner.invoke(app, ["stop", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no stop command defined" in result.output


@pytest.mark.usefixtures("atk_home")
class TestInstallCli:
    """Tests for atk install CLI command."""

    def test_cli_install_single_plugin(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI installs a single plugin."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "touch installed.txt"})

        result = cli_runner.invoke(app, ["install", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "installed.txt").exists()

    def test_cli_install_plugin_not_found(self, cli_runner) -> None:
        """Verify CLI returns PLUGIN_NOT_FOUND for unknown plugin."""
        result = cli_runner.invoke(app, ["install", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_install_all_runs_all_plugins(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify --all installs all plugins in manifest order."""
        plugin1_dir = create_plugin("Plugin1", "plugin-1", {"install": "touch installed1.txt"})
        plugin2_dir = create_plugin("Plugin2", "plugin-2", {"install": "touch installed2.txt"})

        result = cli_runner.invoke(app, ["install", "--all"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin1_dir / "installed1.txt").exists()
        assert (plugin2_dir / "installed2.txt").exists()

    def test_install_all_continues_on_failure(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify --all continues installing after a plugin fails."""
        create_plugin("Plugin1", "plugin-1", {"install": "exit 1"})
        plugin2_dir = create_plugin("Plugin2", "plugin-2", {"install": "touch installed2.txt"})

        result = cli_runner.invoke(app, ["install", "--all"])

        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert (plugin2_dir / "installed2.txt").exists()
        assert "failed" in result.output.lower()

    def test_cli_install_fails_with_missing_required_env_vars(
        self, atk_home: Path, cli_runner
    ) -> None:
        """Verify CLI fails with exit code 8 when required env vars are missing."""
        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        required_var = "REQUIRED_API_KEY"
        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": plugin_name,
            "description": "Test plugin",
            "lifecycle": {"install": "echo installing"},
            "env_vars": [{"name": required_var, "required": True}],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["install", plugin_dir_name])

        assert result.exit_code == exit_codes.ENV_NOT_CONFIGURED
        assert required_var in result.output
        assert "Missing required" in result.output


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


@pytest.mark.usefixtures("atk_home")
class TestRestartCli:
    """Tests for atk restart CLI command."""

    def test_cli_restart_plugin_not_found(self, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        result = cli_runner.invoke(app, ["restart", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

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
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restart --all aborts start phase if stop fails."""
        create_plugin("Plugin1", "plugin1", {"stop": "exit 1", "start": "touch started.txt"})

        result = cli_runner.invoke(app, ["restart", "--all"])

        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert "stop phase had failures" in result.output
        assert "Started plugin" not in result.output

    def test_cli_restart_single_plugin_uses_stop_then_start(
        self, atk_home: Path, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restart <plugin> executes stop then start (not restart command).

        Per Phase 3 spec: There is no restart lifecycle command. The atk restart
        command always executes stop then start in sequence.
        """
        order_file = atk_home / "order.txt"
        stop_cmd = f"echo stop >> {order_file}"
        start_cmd = f"echo start >> {order_file}"
        create_plugin("TestPlugin", "test-plugin", {"stop": stop_cmd, "start": start_cmd})

        result = cli_runner.invoke(app, ["restart", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS, f"Expected SUCCESS, got {result.exit_code}. Output: {result.output}"
        assert order_file.exists(), f"order.txt should exist. Output: {result.output}"
        order = order_file.read_text().strip().split("\n")
        assert order == ["stop", "start"], f"restart should execute stop then start, got {order}"
        assert "Stopped plugin" in result.output
        assert "Started plugin" in result.output


# =============================================================================
# Status Command Tests
# =============================================================================


class TestGetPluginStatus:
    """Tests for get_plugin_status function."""

    def test_returns_running_when_exit_code_zero(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify status is RUNNING when status command exits 0."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        create_plugin("TestPlugin", "test-plugin", {"status": "exit 0"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.RUNNING

    def test_returns_stopped_when_exit_code_nonzero(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify status is STOPPED when status command exits non-zero."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        create_plugin("TestPlugin", "test-plugin", {"status": "exit 1"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.STOPPED

    def test_returns_unknown_when_status_not_defined(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify status is UNKNOWN when no status command defined."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.UNKNOWN

    def test_includes_plugin_name(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify result includes plugin name."""
        from atk.lifecycle import get_plugin_status

        plugin_name = "TestPlugin"
        create_plugin(plugin_name, "test-plugin", {"status": "exit 0"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.name == plugin_name

    def test_includes_ports_from_plugin(
        self, atk_home: Path
    ) -> None:
        """Verify result includes ports from plugin.yaml."""
        from atk.lifecycle import PortStatus, get_plugin_status
        from atk.manifest_schema import PluginEntry, load_manifest, save_manifest

        plugin_dir = atk_home / "plugins" / "test-plugin"
        plugin_dir.mkdir(parents=True)

        port_8080 = 8080
        port_443 = 443
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": "TestPlugin",
            "description": "Test",
            "lifecycle": {"status": "exit 0"},
            "ports": [
                {"port": port_8080, "name": "http"},
                {"port": port_443, "protocol": "https"},
            ],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name="TestPlugin", directory="test-plugin"))
        save_manifest(manifest, atk_home)

        result = get_plugin_status(atk_home, "test-plugin")

        assert len(result.ports) == 2
        assert result.ports[0].port == port_8080
        assert result.ports[1].port == port_443
        assert all(isinstance(p, PortStatus) for p in result.ports)

    def test_port_listening_checked_when_running(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify port listening is checked when status is RUNNING."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        create_plugin(
            "TestPlugin",
            "test-plugin",
            {"status": "exit 0"},
            ports=[{"port": 59999, "name": "test"}],
        )

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.RUNNING
        assert len(result.ports) == 1
        assert result.ports[0].port == 59999
        assert result.ports[0].listening is not None

    def test_port_listening_not_checked_when_stopped(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify port listening is NOT checked when status is STOPPED."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        create_plugin(
            "TestPlugin",
            "test-plugin",
            {"status": "exit 1"},
            ports=[{"port": 59999, "name": "test"}],
        )

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.STOPPED
        assert len(result.ports) == 1
        assert result.ports[0].port == 59999
        assert result.ports[0].listening is None


class TestGetAllPluginsStatus:
    """Tests for get_all_plugins_status function."""

    def test_returns_status_for_all_plugins(
        self, atk_home: Path, create_plugin: PluginFactory
    ) -> None:
        """Verify returns status for each plugin in manifest."""
        from atk.lifecycle import PluginStatus, get_all_plugins_status

        create_plugin("Plugin1", "plugin1", {"status": "exit 0"})
        create_plugin("Plugin2", "plugin2", {"status": "exit 1"})

        results = get_all_plugins_status(atk_home)

        assert len(results) == 2
        assert results[0].name == "Plugin1"
        assert results[0].status == PluginStatus.RUNNING
        assert results[1].name == "Plugin2"
        assert results[1].status == PluginStatus.STOPPED

    def test_returns_empty_list_when_no_plugins(
        self, atk_home: Path
    ) -> None:
        """Verify returns empty list when manifest has no plugins."""
        from atk.lifecycle import get_all_plugins_status

        results = get_all_plugins_status(atk_home)

        assert results == []


@pytest.mark.usefixtures("atk_home")
class TestStatusCli:
    """Tests for atk status CLI command."""

    def test_cli_status_shows_table(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI status shows plugin status in table format."""
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 0"})

        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "TestPlugin" in result.output
        assert "running" in result.output.lower()

    def test_cli_status_shows_stopped(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI status shows stopped plugins."""
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 1"})

        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "stopped" in result.output.lower()

    def test_cli_status_shows_unknown_when_no_status_command(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows unknown for plugins without status command."""
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "unknown" in result.output.lower()

    def test_cli_status_shows_ports(
        self, atk_home: Path, cli_runner
    ) -> None:
        """Verify CLI status shows ports column."""
        from atk.manifest_schema import PluginEntry, load_manifest, save_manifest

        plugin_dir = atk_home / "plugins" / "test-plugin"
        plugin_dir.mkdir(parents=True)
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": "TestPlugin",
            "description": "Test",
            "lifecycle": {"status": "exit 0"},
            "ports": [{"port": 8787}],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name="TestPlugin", directory="test-plugin"))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "8787" in result.output

    def test_cli_status_single_plugin(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI status for a specific plugin."""
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 0"})
        create_plugin("OtherPlugin", "other-plugin", {"status": "exit 1"})

        result = cli_runner.invoke(app, ["status", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "TestPlugin" in result.output
        # Should only show the requested plugin
        assert "OtherPlugin" not in result.output

    def test_cli_status_plugin_not_found(
        self, cli_runner
    ) -> None:
        """Verify CLI returns error when plugin not found."""
        result = cli_runner.invoke(app, ["status", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_cli_status_no_plugins_message(
        self, cli_runner
    ) -> None:
        """Verify CLI shows message when no plugins installed."""
        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no plugins" in result.output.lower()


@pytest.mark.usefixtures("atk_home")
class TestLogsCli:
    """Tests for atk logs CLI command."""

    def test_cli_logs_runs_logs_command(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI logs runs the logs lifecycle command."""
        plugin_dir = create_plugin(
            "TestPlugin", "test-plugin", {"logs": "touch logs_ran.txt"}
        )

        result = cli_runner.invoke(app, ["logs", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "logs_ran.txt").exists()

    def test_cli_logs_plugin_not_found(
        self, cli_runner
    ) -> None:
        """Verify CLI returns error when plugin not found."""
        result = cli_runner.invoke(app, ["logs", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_cli_logs_command_not_defined(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when logs command not defined."""
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        result = cli_runner.invoke(app, ["logs", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no logs command" in result.output.lower()

    def test_cli_logs_requires_plugin_argument(
        self, cli_runner
    ) -> None:
        """Verify CLI requires plugin argument."""
        result = cli_runner.invoke(app, ["logs"])

        assert result.exit_code != exit_codes.SUCCESS


@pytest.mark.usefixtures("atk_home")
class TestRunCli:
    """Tests for atk run CLI command."""

    def test_cli_run_executes_script(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI run executes a script in the plugin directory."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", None)
        script_path = plugin_dir / "my-script.sh"
        script_path.write_text("#!/bin/bash\ntouch script_ran.txt")
        script_path.chmod(0o755)

        result = cli_runner.invoke(app, ["run", "test-plugin", "my-script.sh"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "script_ran.txt").exists()

    def test_cli_run_discovers_script_without_extension(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI run finds script.sh when script name given without extension."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", None)
        script_path = plugin_dir / "my-script.sh"
        script_path.write_text("#!/bin/bash\ntouch discovered.txt")
        script_path.chmod(0o755)

        result = cli_runner.invoke(app, ["run", "test-plugin", "my-script"])

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "discovered.txt").exists()

    def test_cli_run_passes_through_exit_code(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI run passes through script exit code."""
        plugin_dir = create_plugin("TestPlugin", "test-plugin", None)
        script_path = plugin_dir / "failing-script.sh"
        script_path.write_text("#!/bin/bash\nexit 42")
        script_path.chmod(0o755)

        result = cli_runner.invoke(app, ["run", "test-plugin", "failing-script.sh"])

        assert result.exit_code == 42

    def test_cli_run_plugin_not_found(
        self, cli_runner
    ) -> None:
        """Verify CLI returns error when plugin not found."""
        result = cli_runner.invoke(app, ["run", "nonexistent", "script.sh"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_cli_run_script_not_found(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI returns error when script not found."""
        create_plugin("TestPlugin", "test-plugin", None)

        result = cli_runner.invoke(app, ["run", "test-plugin", "nonexistent.sh"])

        assert result.exit_code == exit_codes.GENERAL_ERROR
        assert "not found" in result.output.lower()

    def test_cli_run_requires_both_arguments(
        self, cli_runner
    ) -> None:
        """Verify CLI requires both plugin and script arguments."""
        result = cli_runner.invoke(app, ["run"])
        assert result.exit_code != exit_codes.SUCCESS

        result = cli_runner.invoke(app, ["run", "test-plugin"])
        assert result.exit_code != exit_codes.SUCCESS
