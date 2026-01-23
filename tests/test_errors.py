"""Tests for error formatting utilities."""

from pathlib import Path

import pytest
import yaml
from click.exceptions import Exit
from pydantic import ValidationError
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app, require_initialized_home
from atk.errors import format_validation_errors
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
