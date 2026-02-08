"""Tests for error formatting utilities."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from click.exceptions import Exit
from pydantic import ValidationError
from typer.testing import CliRunner

from atk import cli_logger, exit_codes
from atk.cli import app, require_git, require_initialized_home, require_ready_home
from atk.errors import format_validation_errors, handle_cli_error
from atk.init import init_atk_home
from atk.plugin_schema import PluginSchema

runner = CliRunner()


class TestFormatValidationErrors:
    """Tests for format_validation_errors function."""

    def test_single_missing_field(self) -> None:
        """Verify single missing field produces clean message."""
        # Given - create a validation error by validating incomplete data
        try:
            PluginSchema.model_validate({
                "schema_version": "2026-01-23",
                "name": "Test Plugin",
                # description is missing
            })
            pytest.fail("Expected ValidationError")
        except ValidationError as e:
            # When
            result = format_validation_errors(e)

        # Then - clean message without Pydantic URL
        assert "description" in result
        assert "required" in result.lower()
        assert "pydantic.dev" not in result
        assert "For further information" not in result

    def test_multiple_missing_fields(self) -> None:
        """Verify multiple missing fields are listed clearly."""
        # Given
        try:
            PluginSchema.model_validate({
                "schema_version": "2026-01-23",
                # name and description missing
            })
            pytest.fail("Expected ValidationError")
        except ValidationError as e:
            # When
            result = format_validation_errors(e)

        # Then
        assert "name" in result
        assert "description" in result
        assert "pydantic.dev" not in result

    def test_invalid_type(self) -> None:
        """Verify type errors produce clean message."""
        # Given
        try:
            PluginSchema.model_validate({
                "schema_version": "2026-01-23",
                "name": "Test Plugin",
                "description": "A test",
                "ports": "not a list",  # should be list
            })
            pytest.fail("Expected ValidationError")
        except ValidationError as e:
            # When
            result = format_validation_errors(e)

        # Then
        assert "ports" in result
        assert "pydantic.dev" not in result


class TestCLIErrorMessages:
    """Tests for CLI error message formatting."""

    def test_add_invalid_plugin_shows_clean_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify CLI shows clean error for invalid plugin schema."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # Create invalid plugin (missing description)
        plugin_dir = tmp_path / "bad-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.yaml").write_text(yaml.dump({
            "schema_version": "2026-01-23",
            "name": "Bad Plugin",
            # description missing
        }))

        # When
        result = runner.invoke(app, ["add", str(plugin_dir)])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_INVALID
        assert "description" in result.stdout
        assert "required" in result.stdout.lower()
        # Should NOT contain Pydantic URL
        assert "pydantic.dev" not in result.stdout
        assert "For further information" not in result.stdout

    def test_add_invalid_plugin_multiple_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify CLI shows all validation errors cleanly."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # Create plugin with multiple errors
        plugin_dir = tmp_path / "very-bad-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.yaml").write_text(yaml.dump({
            "schema_version": "2026-01-23",
            # name and description missing
        }))

        # When
        result = runner.invoke(app, ["add", str(plugin_dir)])

        # Then
        assert result.exit_code == exit_codes.PLUGIN_INVALID
        assert "name" in result.stdout
        assert "description" in result.stdout
        assert "pydantic.dev" not in result.stdout


class TestRequireInitializedHome:
    """Tests for require_initialized_home helper."""

    def test_returns_path_when_initialized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify returns ATK Home path when properly initialized."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = require_initialized_home()

        # Then
        assert result == atk_home

    def test_exits_when_not_initialized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify exits with HOME_NOT_INITIALIZED when not initialized."""
        # Given
        atk_home = tmp_path / "not-initialized"
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When/Then - typer.Exit raises click.exceptions.Exit
        with pytest.raises(Exit) as exc_info:
            require_initialized_home()

        assert exc_info.value.exit_code == exit_codes.HOME_NOT_INITIALIZED


class TestRequireGit:
    """Tests for require_git helper."""

    def test_passes_when_git_available(self) -> None:
        """Verify require_git does not exit when git is available."""
        # Given - git is available on the system (test environment assumption)

        # When/Then - should not raise
        require_git()  # No exception = pass

    def test_exits_when_git_not_available(self) -> None:
        """Verify require_git exits with GIT_ERROR when git not found."""
        # Given - mock git as unavailable
        with patch("atk.cli.is_git_available", return_value=False):
            # When/Then
            with pytest.raises(Exit) as exc_info:
                require_git()

            assert exc_info.value.exit_code == exit_codes.GIT_ERROR


class TestRequireReadyHome:
    """Tests for require_ready_home helper."""

    def test_returns_path_when_initialized_and_git_available(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify returns path when home initialized and git available."""
        # Given - initialized home with auto_commit enabled
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = require_ready_home()

        # Then
        assert result == atk_home

    def test_exits_when_home_not_initialized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify exits with HOME_NOT_INITIALIZED when not initialized."""
        # Given
        atk_home = tmp_path / "not-initialized"
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When/Then
        with pytest.raises(Exit) as exc_info:
            require_ready_home()

        assert exc_info.value.exit_code == exit_codes.HOME_NOT_INITIALIZED

    def test_exits_when_git_not_available_and_auto_commit_enabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify exits with GIT_ERROR when auto_commit enabled but git unavailable."""
        # Given - initialized home with auto_commit: true (default)
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When/Then - mock git as unavailable
        with patch("atk.cli.is_git_available", return_value=False):
            with pytest.raises(Exit) as exc_info:
                require_ready_home()

            assert exc_info.value.exit_code == exit_codes.GIT_ERROR

    def test_passes_when_git_not_available_but_auto_commit_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify passes when auto_commit disabled even if git unavailable."""
        # Given - initialized home with auto_commit: false
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # Update manifest to disable auto_commit
        manifest_path = atk_home / "manifest.yaml"
        manifest_content = yaml.safe_load(manifest_path.read_text())
        manifest_content["config"]["auto_commit"] = False
        manifest_path.write_text(yaml.dump(manifest_content))

        # When/Then - mock git as unavailable
        with patch("atk.cli.is_git_available", return_value=False):
            result = require_ready_home()

            # Then - should succeed because auto_commit is disabled
            assert result == atk_home



class TestHandleCliError:
    """Tests for handle_cli_error function."""

    def test_handles_permission_error(self) -> None:
        """Verify PermissionError produces clean message and GENERAL_ERROR exit code."""
        # Given
        filename = "/path/to/script.sh"
        error = PermissionError(13, "Permission denied", filename)

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(error)

        # Then
        expected_exit_code = exit_codes.GENERAL_ERROR
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()
        call_message = mock_error.call_args[0][0]
        assert "Permission denied" in call_message
        assert filename in call_message

    def test_handles_file_not_found_error(self) -> None:
        """Verify FileNotFoundError produces clean message and GENERAL_ERROR exit code."""
        # Given
        filename = "/path/to/missing"
        error = FileNotFoundError(2, "No such file or directory", filename)

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(error)

        # Then
        expected_exit_code = exit_codes.GENERAL_ERROR
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()
        call_message = mock_error.call_args[0][0]
        assert filename in call_message

    def test_handles_called_process_error(self) -> None:
        """Verify CalledProcessError produces clean message and GENERAL_ERROR exit code."""
        # Given
        cmd = ["git", "clone", "https://example.com"]
        returncode = 128
        error = subprocess.CalledProcessError(returncode, cmd)

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(error)

        # Then
        expected_exit_code = exit_codes.GENERAL_ERROR
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()
        call_message = mock_error.call_args[0][0]
        assert str(returncode) in call_message

    def test_handles_validation_error(self) -> None:
        """Verify ValidationError produces clean message and PLUGIN_INVALID exit code."""
        # Given - create a real ValidationError
        captured_error: ValidationError | None = None
        try:
            PluginSchema.model_validate({
                "schema_version": "2026-01-23",
                "name": "Test Plugin",
                # description missing
            })
            pytest.fail("Expected ValidationError")
        except ValidationError as e:
            captured_error = e
        assert captured_error is not None

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(captured_error)

        # Then
        expected_exit_code = exit_codes.PLUGIN_INVALID
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()
        call_message = mock_error.call_args[0][0]
        assert "description" in call_message
        assert "pydantic.dev" not in call_message

    def test_handles_yaml_error(self) -> None:
        """Verify yaml.YAMLError produces clean message and GENERAL_ERROR exit code."""
        # Given
        captured_error: yaml.YAMLError | None = None
        try:
            yaml.safe_load(":\n  :\n    - ][")
        except yaml.YAMLError as e:
            captured_error = e
        assert captured_error is not None

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(captured_error)

        # Then
        expected_exit_code = exit_codes.GENERAL_ERROR
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()

    def test_handles_generic_exception(self) -> None:
        """Verify generic Exception produces clean message and GENERAL_ERROR exit code."""
        # Given
        error_message = "Something went wrong"
        error = RuntimeError(error_message)

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(error)

        # Then
        expected_exit_code = exit_codes.GENERAL_ERROR
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()
        call_message = mock_error.call_args[0][0]
        assert error_message in call_message

    def test_handles_os_error_without_filename(self) -> None:
        """Verify OSError without filename still produces clean message."""
        # Given
        error = OSError("Disk full")

        # When
        with patch.object(cli_logger, "error") as mock_error:
            exit_code = handle_cli_error(error)

        # Then
        expected_exit_code = exit_codes.GENERAL_ERROR
        assert exit_code == expected_exit_code
        mock_error.assert_called_once()
        call_message = mock_error.call_args[0][0]
        assert "Disk full" in call_message