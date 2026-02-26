"""Tests for the `atk run` and `atk help` CLI commands."""

from collections.abc import Callable
from pathlib import Path

import pytest

from atk import exit_codes
from atk.cli import app

# Type alias for the plugin factory fixture
PluginFactory = Callable[..., Path]


class TestRunCommand:
    """Tests for `atk run <plugin> <script>`."""

    def test_injects_env_vars_from_env_file(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Regression test: .env vars must be visible to scripts run via `atk run`.

        Before the fix, subprocess.run was called without env=, so .env vars
        were never injected and the backup script always saw OPENMEMORY_BACKUP_DIR
        as unset even when the user had configured it.
        """
        # Given
        env_var_name = "MY_RUN_TEST_VAR"
        env_var_value = "hello_from_dotenv"
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        script = plugin_dir / "check_env.sh"
        script.write_text(f'#!/bin/sh\necho "${env_var_name}" > env_output.txt\n')
        script.chmod(0o755)

        env_file = plugin_dir / ".env"
        env_file.write_text(f"{env_var_name}={env_var_value}\n")

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "check_env"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        output_file = plugin_dir / "env_output.txt"
        assert output_file.exists(), "Script did not write output file"
        assert output_file.read_text().strip() == env_var_value

    def test_env_file_vars_override_system_env(
        self, create_plugin: PluginFactory, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify .env file vars take precedence over system environment."""
        # Given
        env_var_name = "OVERRIDE_RUN_VAR"
        system_value = "from_system"
        file_value = "from_dotenv"
        monkeypatch.setenv(env_var_name, system_value)

        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        script = plugin_dir / "check_override.sh"
        script.write_text(f'#!/bin/sh\necho "${env_var_name}" > env_output.txt\n')
        script.chmod(0o755)

        env_file = plugin_dir / ".env"
        env_file.write_text(f"{env_var_name}={file_value}\n")

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "check_override"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        output_file = plugin_dir / "env_output.txt"
        assert output_file.read_text().strip() == file_value

    def test_runs_script_without_sh_extension(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify script is found and run when caller omits .sh extension."""
        # Given
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})
        script = plugin_dir / "myscript.sh"
        script.write_text("#!/bin/sh\ntouch ran.txt\n")
        script.chmod(0o755)

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "myscript"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert (plugin_dir / "ran.txt").exists()

    def test_returns_script_exit_code(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify exit code from script is propagated."""
        # Given
        expected_code = 42
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})
        script = plugin_dir / "fail.sh"
        script.write_text(f"#!/bin/sh\nexit {expected_code}\n")
        script.chmod(0o755)

        # When
        result = cli_runner.invoke(app, ["run", "test-plugin", "fail"])

        # Then
        assert result.exit_code == expected_code

    def test_plugin_not_found_returns_error(self, configure_atk_home, cli_runner) -> None:
        """Verify error when plugin does not exist."""
        configure_atk_home()
        result = cli_runner.invoke(app, ["run", "nonexistent-plugin", "backup"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND

    def test_script_not_found_returns_error(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify error when script does not exist in plugin directory."""
        create_plugin("TestPlugin", "test-plugin", {"install": "echo install"})

        result = cli_runner.invoke(app, ["run", "test-plugin", "nonexistent_script"])

        assert result.exit_code == exit_codes.GENERAL_ERROR


class TestHelpCommand:
    """Tests for `atk help <plugin>`."""

    def test_renders_readme_when_present(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify README.md content is rendered when file exists."""
        readme_content = "# My Plugin\n\nThis is the help text."
        plugin_dir = create_plugin("TestPlugin", "test-plugin", {})
        (plugin_dir / "README.md").write_text(readme_content)

        result = cli_runner.invoke(app, ["help", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "My Plugin" in result.output

    def test_warns_when_no_readme(
        self, create_plugin: PluginFactory, cli_runner
    ) -> None:
        """Verify warning and exit 0 when README.md is absent."""
        create_plugin("TestPlugin", "test-plugin", {})

        result = cli_runner.invoke(app, ["help", "test-plugin"])

        assert result.exit_code == exit_codes.SUCCESS
        assert "no README.md" in result.output

    def test_plugin_not_found_returns_error(
        self, configure_atk_home, cli_runner
    ) -> None:
        """Verify PLUGIN_NOT_FOUND when plugin is not in manifest."""
        configure_atk_home()

        result = cli_runner.invoke(app, ["help", "nonexistent-plugin"])

        assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND

