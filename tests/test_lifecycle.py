"""Tests for lifecycle command execution."""

import json
import os
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from atk import exit_codes
from atk.cli import app, format_env_status
from atk.git import read_atk_ref
from atk.lifecycle import (
    LifecycleCommandNotDefinedError,
    get_plugin_status,
    restart_all_plugins,
    run_lifecycle_command,
)
from atk.manifest_schema import PluginEntry, SourceInfo, SourceType, load_manifest, save_manifest
from atk.plugin import load_plugin
from atk.plugin_schema import (
    PLUGIN_SCHEMA_VERSION,
    EnvVarConfig,
    LifecycleConfig,
    McpPluginConfig,
    PluginSchema,
)
from tests.conftest import (
    create_fake_git_repo,
    create_fake_registry,
    update_fake_repo,
    write_plugin_yaml,
)

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


# =============================================================================
# CLI Tests for Lifecycle Commands
# =============================================================================


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

    def test_cli_start_plugin_not_found(self, configure_atk_home, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        configure_atk_home()
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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI fails with exit code 8 when required env vars are missing."""
        atk_home = configure_atk_home()
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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI succeeds when required env var is set in .env file."""
        atk_home = configure_atk_home()
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
        self, configure_atk_home, cli_runner, monkeypatch
    ) -> None:
        """Verify CLI succeeds when required env var is set in system environment."""
        atk_home = configure_atk_home()
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

    def test_cli_start_fails_with_port_conflict(
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI fails with exit code 9 when a declared port is already in use."""
        import socket
        atk_home = configure_atk_home()

        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        conflict_port = 19876
        port_description = "Web UI"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", conflict_port))
        sock.listen(1)

        try:
            plugin_dir = atk_home / "plugins" / plugin_dir_name
            plugin_dir.mkdir(parents=True, exist_ok=True)
            plugin_yaml = {
                "schema_version": PLUGIN_SCHEMA_VERSION,
                "name": plugin_name,
                "description": "Test plugin",
                "lifecycle": {"start": "echo starting"},
                "ports": [{"port": conflict_port, "description": port_description}],
            }
            (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
            manifest = load_manifest(atk_home)
            manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
            save_manifest(manifest, atk_home)

            result = cli_runner.invoke(app, ["start", plugin_dir_name])

            assert result.exit_code == exit_codes.PORT_CONFLICT
            assert str(conflict_port) in result.output
            assert "already in use" in result.output.lower()
        finally:
            sock.close()

    def test_cli_start_succeeds_when_port_is_free(
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI succeeds when declared port is not in use."""
        atk_home = configure_atk_home()
        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        free_port = 19877

        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_yaml = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": plugin_name,
            "description": "Test plugin",
            "lifecycle": {"start": "echo starting"},
            "ports": [{"port": free_port, "description": "API"}],
        }
        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["start", plugin_dir_name])

        assert result.exit_code == exit_codes.SUCCESS
        assert "Started plugin" in result.output


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

    def test_cli_stop_plugin_not_found(self, configure_atk_home, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        configure_atk_home()
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

    def test_cli_install_plugin_not_found(self, configure_atk_home, cli_runner) -> None:
        """Verify CLI returns PLUGIN_NOT_FOUND for unknown plugin."""
        configure_atk_home()
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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI fails with exit code 8 when required env vars are missing."""
        # Given - plugin with required env var
        atk_home = configure_atk_home()
        plugin_name = "TestPlugin"
        plugin_dir_name = "test-plugin"
        required_var = "REQUIRED_API_KEY"
        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name=plugin_name,
            description="Test plugin",
            lifecycle=LifecycleConfig(
                install="echo installing",
                uninstall="echo uninstalling",
            ),
            env_vars=[EnvVarConfig(name=required_var, required=True)],
        )
        write_plugin_yaml(plugin_dir, plugin)

        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=plugin_name, directory=plugin_dir_name))
        save_manifest(manifest, atk_home)

        result = cli_runner.invoke(app, ["install", plugin_dir_name])

        assert result.exit_code == exit_codes.ENV_NOT_CONFIGURED
        assert required_var in result.output
        assert "Missing required" in result.output

    def test_cli_install_pulls_plugin_from_registry(
        self, configure_atk_home, cli_runner, tmp_path: Path
    ) -> None:
        """Verify CLI pulls pinned (older) commit from registry, not latest."""

        # Given - registry with two commits; manifest pins to the first (older) one
        atk_home = configure_atk_home()
        fake_registry = create_fake_registry(tmp_path)
        first_commit = fake_registry.commit_hash
        original_description = "A test plugin from registry"
        update_fake_repo(fake_registry.url, "plugins/test-plugin/plugin.yaml", "v2")

        plugin_name = "Test Plugin"
        plugin_dir_name = "test-plugin"

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(
                name=plugin_name,
                directory=plugin_dir_name,
                source=SourceInfo(type=SourceType.REGISTRY, ref=first_commit),
            )
        )
        save_manifest(manifest, atk_home)

        plugin_dir = atk_home / "plugins" / plugin_dir_name
        assert not plugin_dir.exists()

        # When
        with patch("atk.registry.REGISTRY_URL", fake_registry.url):
            result = cli_runner.invoke(app, ["install", plugin_dir_name])

        # Then - plugin files match the older commit, not latest
        assert result.exit_code == exit_codes.SUCCESS, f"Output: {result.output}"
        assert plugin_dir.exists()
        fetched_data = yaml.safe_load((plugin_dir / "plugin.yaml").read_text())
        assert fetched_data["description"] == original_description
        assert read_atk_ref(plugin_dir) == first_commit

    def test_cli_install_pulls_plugin_from_git(
        self, configure_atk_home, cli_runner, tmp_path: Path
    ) -> None:
        """Verify CLI pulls pinned (latest) commit from git, matching updated content."""

        # Given - git repo with two commits; manifest pins to the second (latest) one
        atk_home = configure_atk_home()
        fake_git = create_fake_git_repo(tmp_path)
        update_message = "v2"
        second_commit = update_fake_repo(fake_git.url, ".atk/plugin.yaml", update_message)
        updated_description = f"Updated — {update_message}"
        plugin_dir_name = "echo-tool"

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(
                name="Echo Tool",
                directory=plugin_dir_name,
                source=SourceInfo(type=SourceType.GIT, url=fake_git.url, ref=second_commit),
            )
        )
        save_manifest(manifest, atk_home)

        plugin_dir = atk_home / "plugins" / plugin_dir_name
        assert not plugin_dir.exists()

        # When
        result = cli_runner.invoke(app, ["install", plugin_dir_name])

        # Then - plugin files match the latest commit
        assert result.exit_code == exit_codes.SUCCESS, f"Output: {result.output}"
        assert plugin_dir.exists()
        fetched_data = yaml.safe_load((plugin_dir / "plugin.yaml").read_text())
        assert fetched_data["description"] == updated_description
        assert read_atk_ref(plugin_dir) == second_commit

    def test_cli_install_pulls_plugin_and_preserves_custom_dir(
        self, configure_atk_home, cli_runner, tmp_path: Path
    ) -> None:
        """Verify CLI pulls pinned (older) commit and preserves custom/ directory."""
        # Given - registry with two commits; manifest pins to the first (older) one
        atk_home = configure_atk_home()
        fake_registry = create_fake_registry(tmp_path)
        first_commit = fake_registry.commit_hash
        original_description = "A test plugin from registry"
        update_fake_repo(fake_registry.url, "plugins/test-plugin/plugin.yaml", "v2")
        plugin_dir_name = "test-plugin"

        # And - plugin directory exists with custom/ directory containing user files
        plugin_dir = atk_home / "plugins" / plugin_dir_name
        plugin_dir.mkdir(parents=True)
        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        custom_file = custom_dir / "my-override.yaml"
        custom_content = "user: customization"
        custom_file.write_text(custom_content)

        # And - plugin is in manifest but files not pulled (bootstrap scenario)
        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(
                name="Test Plugin",
                directory=plugin_dir_name,
                source=SourceInfo(type=SourceType.REGISTRY, ref=first_commit),
            )
        )
        save_manifest(manifest, atk_home)

        assert not (plugin_dir / "plugin.yaml").exists()
        assert custom_file.exists()

        # When
        with patch("atk.registry.REGISTRY_URL", fake_registry.url):
            result = cli_runner.invoke(app, ["install", plugin_dir_name])

        # Then - plugin files match the older commit
        assert result.exit_code == exit_codes.SUCCESS, f"Output: {result.output}"
        fetched_data = yaml.safe_load((plugin_dir / "plugin.yaml").read_text())
        assert fetched_data["description"] == original_description
        assert read_atk_ref(plugin_dir) == first_commit

        # And - custom/ directory is preserved
        assert custom_file.exists()
        assert custom_file.read_text() == custom_content

    def test_cli_install_all_pulls_all_missing_plugins(
        self, configure_atk_home, cli_runner, tmp_path: Path, create_plugin) -> None:
        """Verify install --all: registry pinned to older commit, git pinned to latest."""

        # Given - registry with two commits; pin to older
        atk_home = configure_atk_home()
        fake_registry = create_fake_registry(tmp_path)
        registry_first_commit = fake_registry.commit_hash
        registry_original_desc = "A test plugin from registry"
        update_fake_repo(fake_registry.url, "plugins/test-plugin/plugin.yaml", "reg-v2")
        registry_plugin_dir = "test-plugin"

        # And - git repo with two commits; pin to latest
        git_tmp = tmp_path / "git-repo"
        git_tmp.mkdir()
        fake_git = create_fake_git_repo(git_tmp)
        git_update_msg = "git-v2"
        git_second_commit = update_fake_repo(fake_git.url, ".atk/plugin.yaml", git_update_msg)
        git_updated_desc = f"Updated — {git_update_msg}"
        git_plugin_dir = "echo-tool"

        # And - local plugin (already exists)
        local_plugin_dir = create_plugin(
            "Local Plugin",
            "local-plugin",
            {"install": "touch installed.txt", "uninstall": "echo uninstall"},
        )

        manifest = load_manifest(atk_home)
        manifest.plugins = [
            PluginEntry(
                name="Test Plugin",
                directory=registry_plugin_dir,
                source=SourceInfo(type=SourceType.REGISTRY, ref=registry_first_commit),
            ),
            PluginEntry(
                name="Echo Tool",
                directory=git_plugin_dir,
                source=SourceInfo(type=SourceType.GIT, url=fake_git.url, ref=git_second_commit),
            ),
            PluginEntry(
                name="Local Plugin",
                directory="local-plugin",
                source=SourceInfo(type=SourceType.LOCAL),
            ),
        ]
        save_manifest(manifest, atk_home)

        registry_dir = atk_home / "plugins" / registry_plugin_dir
        git_dir = atk_home / "plugins" / git_plugin_dir
        assert not registry_dir.exists()
        assert not git_dir.exists()
        assert local_plugin_dir.exists()

        # When
        with patch("atk.registry.REGISTRY_URL", fake_registry.url):
            result = cli_runner.invoke(app, ["install", "--all"])

        # Then - registry plugin has older content
        assert result.exit_code == exit_codes.SUCCESS, f"Output: {result.output}"
        reg_data = yaml.safe_load((registry_dir / "plugin.yaml").read_text())
        assert reg_data["description"] == registry_original_desc
        assert read_atk_ref(registry_dir) == registry_first_commit

        # And - git plugin has latest content
        git_data = yaml.safe_load((git_dir / "plugin.yaml").read_text())
        assert git_data["description"] == git_updated_desc
        assert read_atk_ref(git_dir) == git_second_commit

        # And - local plugin ran its install script
        assert (local_plugin_dir / "installed.txt").exists()


class TestUninstallCli:
    """Tests for atk uninstall CLI command."""

    def test_cli_uninstall_single_plugin(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI uninstalls a single plugin with --force flag."""
        # Given - plugin with uninstall lifecycle
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {"install": "touch installed.txt", "uninstall": "touch uninstalled.txt"},
        )

        # When
        result = cli_runner.invoke(app, ["uninstall", "test-plugin", "--force"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "Uninstalled" in result.output
        assert (plugin_dir / "uninstalled.txt").exists()

    def test_cli_uninstall_plugin_not_found(self, configure_atk_home, cli_runner) -> None:
        """Verify CLI returns PLUGIN_NOT_FOUND for unknown plugin."""
        configure_atk_home()
        # Given - no plugin installed

        # When
        result = cli_runner.invoke(app, ["uninstall", "nonexistent", "--force"])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_cli_uninstall_shows_warning_when_not_defined(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI shows warning when uninstall command not defined."""
        # Given - plugin without uninstall lifecycle
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        # When
        result = cli_runner.invoke(app, ["uninstall", "test-plugin", "--force"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "no uninstall command defined" in result.output

    def test_cli_uninstall_runs_stop_before_uninstall(
        self, configure_atk_home, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify uninstall runs stop lifecycle before uninstall."""
        # Given - plugin with stop and uninstall lifecycles that write to order file
        atk_home = configure_atk_home()
        order_file = atk_home / "order.txt"
        expected_order = ["stop", "uninstall"]
        create_plugin(
            "TestPlugin",
            "test-plugin",
            {
                "install": "echo install",
                "uninstall": f"echo {expected_order[1]} >> {order_file}",
                "stop": f"echo {expected_order[0]} >> {order_file}",
            },
        )

        # When
        result = cli_runner.invoke(app, ["uninstall", "test-plugin", "--force"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        order = order_file.read_text().strip().split("\n")
        assert order == expected_order

    def test_cli_uninstall_continues_when_stop_fails(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify uninstall continues even if stop fails."""
        # Given - plugin with failing stop lifecycle
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {
                "install": "echo install",
                "uninstall": "touch uninstalled.txt",
                "stop": "exit 1",
            },
        )

        # When
        result = cli_runner.invoke(app, ["uninstall", "test-plugin", "--force"])

        # Then - uninstall still runs despite stop failure
        assert result.exit_code == exit_codes.SUCCESS
        assert "Stop failed" in result.output
        assert (plugin_dir / "uninstalled.txt").exists()

    def test_cli_uninstall_prompts_for_confirmation(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify uninstall prompts for confirmation without --force."""
        # Given - plugin with uninstall lifecycle
        create_plugin(
            "TestPlugin",
            "test-plugin",
            {"install": "echo install", "uninstall": "echo uninstalling"},
        )

        # When - user cancels confirmation
        result = cli_runner.invoke(app, ["uninstall", "test-plugin"], input="n\n")

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "Continue?" in result.output
        assert "cancelled" in result.output.lower()

    def test_cli_uninstall_accepts_confirmation(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify uninstall proceeds when user confirms."""
        # Given - plugin with uninstall lifecycle
        plugin_dir = create_plugin(
            "TestPlugin",
            "test-plugin",
            {"install": "echo install", "uninstall": "touch uninstalled.txt"},
        )

        # When - user confirms
        result = cli_runner.invoke(app, ["uninstall", "test-plugin"], input="y\n")

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "uninstalled.txt").exists()


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


class TestRestartCli:
    """Tests for atk restart CLI command."""

    def test_cli_restart_plugin_not_found(self, configure_atk_home, cli_runner) -> None:
        """Verify CLI reports error when plugin not found."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["restart", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output

    def test_cli_restart_all_stops_then_starts(
        self, configure_atk_home, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restart --all stops all then starts all."""
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
        self, configure_atk_home, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify CLI restart <plugin> executes stop then start (not restart command).

        Per Phase 3 spec: There is no restart lifecycle command. The atk restart
        command always executes stop then start in sequence.
        """
        atk_home = configure_atk_home()
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
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify status is RUNNING when status command exits 0."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 0"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.RUNNING

    def test_returns_stopped_when_exit_code_nonzero(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify status is STOPPED when status command exits non-zero."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"status": "exit 1"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.STOPPED

    def test_returns_unknown_when_status_not_defined(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify status is UNKNOWN when no status command defined."""
        from atk.lifecycle import PluginStatus, get_plugin_status

        atk_home = configure_atk_home()
        create_plugin("TestPlugin", "test-plugin", {"start": "echo start"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.status == PluginStatus.UNKNOWN

    def test_includes_plugin_name(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify result includes plugin name."""
        from atk.lifecycle import get_plugin_status

        atk_home = configure_atk_home()
        plugin_name = "TestPlugin"
        create_plugin(plugin_name, "test-plugin", {"status": "exit 0"})

        result = get_plugin_status(atk_home, "test-plugin")

        assert result.name == plugin_name

    def test_includes_ports_from_plugin(
        self, configure_atk_home
    ) -> None:
        """Verify result includes ports from plugin.yaml."""
        from atk.lifecycle import PortStatus, get_plugin_status
        from atk.manifest_schema import PluginEntry, load_manifest, save_manifest

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
        from atk.lifecycle import PluginStatus, get_plugin_status

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
        from atk.lifecycle import PluginStatus, get_plugin_status

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


class TestFormatEnvStatus:
    """Tests for format_env_status helper function."""

    def test_shows_checkmark_when_all_required_set_with_unset_optional(self) -> None:
        """Verify checkmark shown when all required vars set (even with unset optional vars).

        Regression test: Bug where function returned "-" instead of "✓" when
        all required vars were set but optional vars were unset.
        """
        # Given
        missing_required_vars = []
        unset_optional_count = 1
        total_env_vars = 2
        expected_result = "[green]✓[/green]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_checkmark_when_all_vars_set(self) -> None:
        """Verify checkmark shown when all vars (required and optional) are set."""
        # Given
        missing_required_vars = []
        unset_optional_count = 0
        total_env_vars = 2
        expected_result = "[green]✓[/green]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_dash_when_no_env_vars_defined(self) -> None:
        """Verify dash shown when plugin has no env vars defined."""
        # Given
        missing_required_vars = []
        unset_optional_count = 0
        total_env_vars = 0
        expected_result = "-"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_missing_required_vars_by_name(self) -> None:
        """Verify missing required vars are listed by name."""
        # Given
        var1_name = "API_KEY"
        var2_name = "SECRET_KEY"
        missing_required_vars = [var1_name, var2_name]
        unset_optional_count = 0
        total_env_vars = 3
        expected_result = f"[red]! {var1_name}, {var2_name}[/red]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_optional_count_with_missing_required(self) -> None:
        """Verify optional count shown when required vars missing."""
        # Given
        var_name = "API_KEY"
        missing_required_vars = [var_name]
        unset_optional_count = 2
        total_env_vars = 3
        expected_result = f"[red]! {var_name}[/red] [dim](+{unset_optional_count} optional)[/dim]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result


class TestGetAllPluginsStatus:
    """Tests for get_all_plugins_status function."""

    def test_returns_status_for_all_plugins(
        self, configure_atk_home, create_plugin: PluginFactory
    ) -> None:
        """Verify returns status for each plugin in manifest."""
        from atk.lifecycle import PluginStatus, get_all_plugins_status

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
        from atk.lifecycle import get_all_plugins_status

        atk_home = configure_atk_home()
        results = get_all_plugins_status(atk_home)

        assert results == []


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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI status shows ports column."""
        from atk.manifest_schema import PluginEntry, load_manifest, save_manifest

        atk_home = configure_atk_home()
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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI returns error when plugin not found."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["status", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_cli_status_no_plugins_message(
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI shows message when no plugins installed."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["status"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no plugins" in result.output.lower()


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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI returns error when plugin not found."""
        configure_atk_home()
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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI requires plugin argument."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["logs"])

        assert result.exit_code != exit_codes.SUCCESS


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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI returns error when plugin not found."""
        configure_atk_home()
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
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify CLI requires both plugin and script arguments."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["run"])
        assert result.exit_code != exit_codes.SUCCESS

        result = cli_runner.invoke(app, ["run", "test-plugin"])
        assert result.exit_code != exit_codes.SUCCESS

    def test_cli_run_prefers_custom_script_over_root(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Script in custom/ takes precedence over same script in plugin root."""
        # Given - script exists in both custom/ and root, with different behavior
        plugin_dir = create_plugin("TestPlugin", "test-plugin", None)
        root_script = plugin_dir / "my-script.sh"
        root_script.write_text("#!/bin/bash\ntouch root_ran.txt")
        root_script.chmod(0o755)

        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        custom_script = custom_dir / "my-script.sh"
        custom_script.write_text("#!/bin/bash\ntouch custom_ran.txt")
        custom_script.chmod(0o755)

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "my-script.sh"])

        # Then - custom/ version ran, not root version
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "custom_ran.txt").exists()
        assert not (plugin_dir / "root_ran.txt").exists()

    def test_cli_run_falls_back_to_root_when_not_in_custom(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Script only in root still works when custom/ exists but doesn't have it."""
        # Given - script only in root, custom/ directory exists but empty
        plugin_dir = create_plugin("TestPlugin", "test-plugin", None)
        root_script = plugin_dir / "my-script.sh"
        root_script.write_text("#!/bin/bash\ntouch root_ran.txt")
        root_script.chmod(0o755)
        (plugin_dir / "custom").mkdir()

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "my-script.sh"])

        # Then - root version ran
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "root_ran.txt").exists()

    def test_cli_run_finds_script_only_in_custom(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Script only in custom/ is found and executed."""
        # Given - script only in custom/, not in root
        plugin_dir = create_plugin("TestPlugin", "test-plugin", None)
        custom_dir = plugin_dir / "custom"
        custom_dir.mkdir()
        custom_script = custom_dir / "my-script.sh"
        custom_script.write_text("#!/bin/bash\ntouch custom_only_ran.txt")
        custom_script.chmod(0o755)

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "my-script.sh"])

        # Then - custom/ version ran
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "custom_only_ran.txt").exists()


class TestSetupCli:
    """Tests for atk setup CLI command."""

    def test_cli_setup_prompts_for_env_vars_and_saves(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify atk setup prompts for each env var and saves to .env file."""
        plugin_dir_name = "test-plugin"
        var1_name = "API_KEY"
        var1_value = "my-api-key"
        var2_name = "DEBUG_MODE"
        var2_value = "true"

        plugin_dir = create_plugin(
            "TestPlugin",
            plugin_dir_name,
            env_vars=[
                EnvVarConfig(name=var1_name, required=True),
                EnvVarConfig(name=var2_name, required=False),
            ],
        )

        result = cli_runner.invoke(
            app, ["setup", plugin_dir_name], input=f"{var1_value}\n{var2_value}\n"
        )

        assert result.exit_code == exit_codes.SUCCESS
        env_file = plugin_dir / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert content == f"{var1_name}={var1_value}\n{var2_name}={var2_value}\n"

    def test_cli_setup_plugin_not_found(self, configure_atk_home, cli_runner) -> None:
        """Verify atk setup fails when plugin not found."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["setup", "nonexistent"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
        assert "not found" in result.output.lower()

    def test_cli_setup_all_configures_multiple_plugins(
        self,create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify atk setup --all configures all plugins with env vars."""
        plugin1_var = "PLUGIN1_KEY"
        plugin1_value = "value1"
        plugin2_var = "PLUGIN2_KEY"
        plugin2_value = "value2"

        plugin1_dir = create_plugin(
            "Plugin1",
            "plugin1",
            env_vars=[EnvVarConfig(name=plugin1_var, required=True)],
        )
        plugin2_dir = create_plugin(
            "Plugin2",
            "plugin2",
            env_vars=[EnvVarConfig(name=plugin2_var, required=True)],
        )

        result = cli_runner.invoke(
            app, ["setup", "--all"], input=f"{plugin1_value}\n{plugin2_value}\n"
        )

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin1_dir / ".env").read_text() == f"{plugin1_var}={plugin1_value}\n"
        assert (plugin2_dir / ".env").read_text() == f"{plugin2_var}={plugin2_value}\n"

    def test_cli_setup_skips_plugins_without_env_vars(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify atk setup --all skips plugins with no env vars defined."""
        var_name = "MY_VAR"
        var_value = "my-value"

        plugin_with_vars_dir = create_plugin(
            "PluginWithVars",
            "plugin-with-vars",
            env_vars=[EnvVarConfig(name=var_name)],
        )
        plugin_without_vars_dir = create_plugin(
            "PluginWithoutVars",
            "plugin-without-vars",
        )

        result = cli_runner.invoke(app, ["setup", "--all"], input=f"{var_value}\n")

        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_with_vars_dir / ".env").exists()
        assert not (plugin_without_vars_dir / ".env").exists()


class TestMcpCli:
    """Tests for atk mcp CLI command."""

    def test_cli_mcp_outputs_json_for_stdio_transport(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify atk mcp outputs valid JSON with command, args, and resolved env vars."""
        # Given
        plugin_name = "TestMcp"
        plugin_dir_name = "test-mcp"
        var_name = "API_KEY"
        var_value = "my-api-key"
        mcp_command = "docker"
        mcp_args = ["exec", "-i", "container", "npx", "server"]

        plugin_dir = create_plugin(
            plugin_name,
            plugin_dir_name,
            mcp=McpPluginConfig(
                transport="stdio",
                command=mcp_command,
                args=mcp_args,
                env=[var_name],
            ),
        )
        (plugin_dir / ".env").write_text(f"{var_name}={var_value}\n")

        # When
        result = cli_runner.invoke(app, ["mcp", plugin_dir_name, "--json"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        output = json.loads(result.output)
        expected = {
            plugin_name: {
                "command": mcp_command,
                "args": mcp_args,
                "env": {var_name: var_value},
            }
        }
        assert output == expected

    def test_cli_mcp_fails_when_no_mcp_config(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify atk mcp fails with exit code 5 when plugin has no MCP config."""
        # Given
        plugin_name = "NoMcpPlugin"
        plugin_dir_name = "no-mcp-plugin"
        create_plugin(plugin_name, plugin_dir_name)

        # When
        result = cli_runner.invoke(app, ["mcp", plugin_dir_name])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_INVALID
        assert "no mcp configuration" in result.output.lower()

    def test_cli_mcp_warns_on_missing_env_vars(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify missing env vars produce warning and <NOT_SET> placeholder."""
        # Given
        plugin_name = "MissingEnvPlugin"
        plugin_dir_name = "missing-env-plugin"
        var_name = "MISSING_VAR"

        create_plugin(
            plugin_name,
            plugin_dir_name,
            mcp=McpPluginConfig(transport="stdio", command="echo", env=[var_name]),
        )

        # When
        result = cli_runner.invoke(app, ["mcp", plugin_dir_name, "--json"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert f"'{var_name}' is not set" in result.output
        json_start = result.output.find("{")
        json_output = result.output[json_start:]
        output = json.loads(json_output)
        assert output[plugin_name]["env"][var_name] == "<NOT_SET>"

    def test_cli_mcp_outputs_url_for_sse_transport(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify SSE transport outputs url field instead of command/args."""
        # Given
        plugin_name = "SsePlugin"
        plugin_dir_name = "sse-plugin"
        endpoint_url = "http://localhost:8080/sse"

        create_plugin(
            plugin_name,
            plugin_dir_name,
            mcp=McpPluginConfig(transport="sse", endpoint=endpoint_url),
        )

        # When
        result = cli_runner.invoke(app, ["mcp", plugin_dir_name, "--json"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        output = json.loads(result.output)
        expected = {plugin_name: {"url": endpoint_url}}
        assert output == expected
        assert "command" not in output[plugin_name]
        assert "args" not in output[plugin_name]

    def test_cli_mcp_substitutes_atk_plugin_dir(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify $ATK_PLUGIN_DIR is substituted with absolute path in MCP config."""
        # Given
        plugin_name = "Piper"
        plugin_dir_name = "piper"
        command = "$ATK_PLUGIN_DIR/mcp-server.sh"
        args = ["--config", "${ATK_PLUGIN_DIR}/config.json"]

        plugin_dir = create_plugin(
            plugin_name,
            plugin_dir_name,
            mcp=McpPluginConfig(
                transport="stdio",
                command=command,
                args=args,
            ),
        )

        # When
        result = cli_runner.invoke(app, ["mcp", plugin_dir_name, "--json"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        output = json.loads(result.output)

        # Verify substitution happened
        plugin_dir_str = str(plugin_dir.resolve())
        expected = {
            plugin_name: {
                "command": f"{plugin_dir_str}/mcp-server.sh",
                "args": ["--config", f"{plugin_dir_str}/config.json"],
            }
        }
        assert output == expected
