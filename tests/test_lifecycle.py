"""Tests for lifecycle business-logic: run_lifecycle_command, restart_all, get_plugin_status."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from atk.lifecycle import (
    LifecycleCommandNotDefinedError,
    PluginStatus,
    PortStatus,
    get_all_plugins_status,
    get_plugin_status,
    restart_all_plugins,
    run_lifecycle_command,
)
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin import load_plugin
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION

# Type alias for the plugin factory fixture
PluginFactory = Callable[..., Path]


class TestRunLifecycleCommand:
    """Tests for run_lifecycle_command function."""

    def test_runs_install_command(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify run_lifecycle_command executes install command."""
        # Given
        atk_home = configure_atk_home()
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "touch installed.txt"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == 0
        assert (plugin_dir / "installed.txt").exists()

    def test_runs_command_in_plugin_directory(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify command runs with plugin directory as cwd."""
        # Given
        atk_home = configure_atk_home()
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "pwd > cwd.txt"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == 0
        cwd_content = (plugin_dir / "cwd.txt").read_text().strip()
        assert cwd_content == str(plugin_dir)

    def test_returns_command_exit_code(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify run_lifecycle_command returns command's exit code."""
        # Given
        atk_home = configure_atk_home()
        expected_exit_code = 42
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": f"exit {expected_exit_code}"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "install")

        # Then
        assert exit_code == expected_exit_code

    def test_raises_when_command_not_defined(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify raises LifecycleCommandNotDefinedError when command missing."""
        # Given
        atk_home = configure_atk_home()
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "echo hello"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When/Then
        with pytest.raises(LifecycleCommandNotDefinedError, match="start"):
            run_lifecycle_command(plugin, plugin_dir, "start")

    def test_raises_when_lifecycle_section_missing(self, configure_atk_home) -> None:
        """Verify raises error when plugin has no lifecycle section."""
        # Given - plugin without lifecycle section (manual creation)
        atk_home = configure_atk_home()
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

    def test_runs_start_command(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify run_lifecycle_command executes start command."""
        # Given
        atk_home = configure_atk_home()
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"start": "touch started.txt"})
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        assert (plugin_dir / "started.txt").exists()

    def test_injects_env_vars_from_env_file(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify run_lifecycle_command injects env vars from .env file."""
        # Given
        atk_home = configure_atk_home()
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
        self, configure_atk_home, create_plugin: PluginFactory, monkeypatch
    ) -> None:
        """Verify .env file vars take precedence over system environment."""
        # Given
        atk_home = configure_atk_home()
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
        self, configure_atk_home, create_plugin: PluginFactory, monkeypatch
    ) -> None:
        """Verify system environment is available when no .env file exists."""
        # Given
        atk_home = configure_atk_home()
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

    def test_includes_compose_override_when_present(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Compose override file is auto-included when running docker compose commands."""
        # Given — lifecycle command uses docker compose, and override file exists
        atk_home = configure_atk_home()
        plugin_dir = create_plugin(
            "TestPlugin", "test-plugin", {"start": "docker compose up -d"}
        )
        plugin, _ = load_plugin(atk_home, "test-plugin")

        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        (custom_dir / "docker-compose.override.yml").write_text("services: {}")

        # Create a fake docker script that logs the full command
        fake_docker = plugin_dir / "docker"
        fake_docker.write_text('#!/bin/bash\necho "$0 $@" > command_log.txt\n')
        fake_docker.chmod(0o755)

        # Prepend plugin_dir to PATH so our fake docker is found first
        original_path = os.environ.get("PATH", "")
        env_file = plugin_dir / ".env"
        env_file.write_text(f"PATH={plugin_dir}:{original_path}\n")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then
        assert exit_code == 0
        command_log = (plugin_dir / "command_log.txt").read_text().strip()
        override_path = "custom/docker-compose.override.yml"
        assert "-f docker-compose.yml" in command_log
        assert f"-f {override_path}" in command_log

    def test_compose_command_unchanged_when_no_override(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Compose command is not modified when no override file exists."""
        # Given — lifecycle command uses docker compose, but no override file
        atk_home = configure_atk_home()
        plugin_dir = create_plugin(
            "TestPlugin", "test-plugin", {"start": "docker compose up -d"}
        )
        plugin, _ = load_plugin(atk_home, "test-plugin")

        # Create a fake docker script that logs the full command
        fake_docker = plugin_dir / "docker"
        fake_docker.write_text('#!/bin/bash\necho "$0 $@" > command_log.txt\n')
        fake_docker.chmod(0o755)

        original_path = os.environ.get("PATH", "")
        env_file = plugin_dir / ".env"
        env_file.write_text(f"PATH={plugin_dir}:{original_path}\n")

        # When
        exit_code = run_lifecycle_command(plugin, plugin_dir, "start")

        # Then — command should NOT have -f flags injected
        assert exit_code == 0
        command_log = (plugin_dir / "command_log.txt").read_text().strip()
        assert "-f" not in command_log


class TestRestartAll:
    """Tests for restart_all_plugins function."""

    def test_restart_all_stops_then_starts(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify restart_all_plugins stops all (reverse), then starts all (forward)."""
        atk_home = configure_atk_home()
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

    def test_restart_all_stops_even_when_start_missing(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify restart_all stops plugins even if they have no start command."""
        atk_home = configure_atk_home()
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

    def test_restart_all_aborts_start_phase_on_stop_failure(self, configure_atk_home, create_plugin: PluginFactory) -> None:
        """Verify restart_all aborts start phase if stop phase has failures."""
        atk_home = configure_atk_home()
        create_plugin("Plugin1", "plugin1", {"stop": "exit 1", "start": "touch started.txt"})

        result = restart_all_plugins(atk_home)

        assert result.all_succeeded is False
        assert len(result.stop_failed) == 1

# =============================================================================
# Status Command Tests
# =============================================================================


class TestGetPluginStatus:
    """Tests for get_plugin_status function."""

    def test_returns_running_when_exit_code_zero(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify status is RUNNING when status command exits 0."""
        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 0"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.RUNNING

    def test_returns_stopped_when_exit_code_nonzero(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify status is STOPPED when status command exits non-zero."""
        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 1"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.STOPPED

    def test_returns_unknown_when_status_not_defined(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify status is UNKNOWN when no status command defined."""
        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.UNKNOWN

    def test_includes_plugin_name(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify result includes plugin name."""
        atk_home = configure_atk_home()
        plugin_name = "TestPlugin"
        create_plugin(plugin_name, "test-plugin", {"status": "exit 0"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.name == plugin_name

    def test_includes_ports_from_plugin(
        self, configure_atk_home
    ) -> None:
        """Verify result includes ports from plugin.yaml."""
        atk_home = configure_atk_home()
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
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify port listening is checked when status is RUNNING."""
        atk_home = configure_atk_home()
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
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify port listening is NOT checked when status is STOPPED."""
        atk_home = configure_atk_home()
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

    def test_env_status_all_required_set(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify env_status shows all required vars set."""
        # Given
        atk_home = configure_atk_home()
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {"status": "exit 0"},
            env_vars=[
                {"name": "API_KEY", "required": True, "secret": True},
                {"name": "OPTIONAL_VAR", "required": False, "secret": False},
            ],
        )
        env_file = plugin_dir / ".env"
        env_file.write_text("API_KEY=test-key\n")
        expected_missing_required = []
        expected_unset_optional = 1
        expected_total_env_vars = 2

        # When
        result = get_plugin_status(atk_home, "test-plugin")

        # Then
        assert result.missing_required_vars == expected_missing_required
        assert result.unset_optional_count == expected_unset_optional
        assert result.total_env_vars == expected_total_env_vars

    def test_env_status_missing_required_vars(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify env_status shows missing required vars by name."""
        # Given
        atk_home = configure_atk_home()
        var1_name = "API_KEY"
        var2_name = "SECRET_KEY"
        create_plugin(
            "TestPlugin",
            "test-plugin",
            {"status": "exit 0"},
            env_vars=[
                {"name": var1_name, "required": True, "secret": True},
                {"name": var2_name, "required": True, "secret": True},
                {"name": "OPTIONAL_VAR", "required": False, "secret": False},
            ],
        )
        expected_missing_required = [var1_name, var2_name]
        expected_unset_optional = 1
        expected_total_env_vars = 3

        # When
        result = get_plugin_status(atk_home, "test-plugin")

        # Then
        assert result.missing_required_vars == expected_missing_required
        assert result.unset_optional_count == expected_unset_optional
        assert result.total_env_vars == expected_total_env_vars

    def test_env_status_no_env_vars_defined(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify env_status when plugin has no env vars."""
        # Given
        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 0"})
        expected_missing_required = []
        expected_unset_optional = 0
        expected_total_env_vars = 0

        # When
        result = get_plugin_status(atk_home, "test-plugin")

        # Then
        assert result.missing_required_vars == expected_missing_required
        assert result.unset_optional_count == expected_unset_optional
        assert result.total_env_vars == expected_total_env_vars


class TestGetAllPluginsStatus:
    """Tests for get_all_plugins_status function."""

    def test_returns_status_for_all_plugins(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify returns status for each plugin in manifest."""
        atk_home = configure_atk_home()
        create_plugin("Plugin1", "plugin1", {"status": "exit 0"})
        create_plugin("Plugin2", "plugin2", {"status": "exit 1"})

        results = get_all_plugins_status(atk_home)

        assert len(results) == 2
        assert results[0].name == "Plugin1"
        assert results[0].status == PluginStatus.RUNNING
        assert results[1].name == "Plugin2"
        assert results[1].status == PluginStatus.STOPPED

    def test_returns_empty_list_when_no_plugins(
        self, configure_atk_home
    ) -> None:
        """Verify returns empty list when manifest has no plugins."""
        atk_home = configure_atk_home()
        results = get_all_plugins_status(atk_home)

        assert results == []

