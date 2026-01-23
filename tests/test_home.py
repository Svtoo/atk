"""Tests for ATK Home resolution and validation."""

from pathlib import Path

import pytest

from atk.home import (
    ATKHomeNotInitializedError,
    get_atk_home,
    validate_atk_home,
)
from atk.validation import ValidationResult


class TestGetAtkHome:
    """Tests for ATK Home path resolution."""

    @pytest.fixture(autouse=True)
    def clear_atk_home_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clear ATK_HOME env var before each test."""
        monkeypatch.delenv("ATK_HOME", raising=False)

    def test_returns_atk_home_env_var_when_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify ATK_HOME env var takes precedence."""
        # Given
        custom_path = "/custom/atk/path"
        monkeypatch.setenv("ATK_HOME", custom_path)

        # When
        result = get_atk_home()

        # Then
        assert result == Path(custom_path)

    def test_returns_default_when_env_var_not_set(self) -> None:
        """Verify default ~/.atk/ is used when ATK_HOME not set."""
        # Given
        expected_default = Path.home() / ".atk"

        # When
        result = get_atk_home()

        # Then
        assert result == expected_default

    def test_expands_tilde_in_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify ~ is expanded in ATK_HOME."""
        # Given
        monkeypatch.setenv("ATK_HOME", "~/my-atk")
        expected = Path.home() / "my-atk"

        # When
        result = get_atk_home()

        # Then
        assert result == expected


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result_is_truthy(self) -> None:
        """Verify valid result evaluates to True in boolean context."""
        # Given/When
        result = ValidationResult(is_valid=True, errors=[])

        # Then
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_result_has_errors(self) -> None:
        """Verify invalid result contains error messages."""
        # Given
        error_msg = "Something went wrong"

        # When
        result = ValidationResult(is_valid=False, errors=[error_msg])

        # Then
        assert result.is_valid is False
        assert error_msg in result.errors


class TestValidateAtkHome:
    """Tests for ATK Home validation."""

    def test_valid_atk_home(self, tmp_path: Path) -> None:
        """Verify valid ATK Home is recognized."""
        # Given - create valid ATK Home structure
        atk_home = tmp_path / ".atk"
        atk_home.mkdir()
        (atk_home / "manifest.yaml").touch()
        (atk_home / "plugins").mkdir()
        (atk_home / ".git").mkdir()

        # When
        result = validate_atk_home(atk_home)

        # Then
        assert result.is_valid is True
        assert result.errors == []

    def test_invalid_missing_manifest(self, tmp_path: Path) -> None:
        """Verify ATK Home without manifest.yaml reports specific error."""
        # Given
        atk_home = tmp_path / ".atk"
        atk_home.mkdir()
        (atk_home / "plugins").mkdir()
        (atk_home / ".git").mkdir()
        # Note: manifest.yaml is missing

        # When
        result = validate_atk_home(atk_home)

        # Then
        assert result.is_valid is False
        assert any("manifest.yaml" in err for err in result.errors)

    def test_invalid_missing_plugins_dir(self, tmp_path: Path) -> None:
        """Verify ATK Home without plugins/ directory reports specific error."""
        # Given
        atk_home = tmp_path / ".atk"
        atk_home.mkdir()
        (atk_home / "manifest.yaml").touch()
        (atk_home / ".git").mkdir()
        # Note: plugins/ is missing

        # When
        result = validate_atk_home(atk_home)

        # Then
        assert result.is_valid is False
        assert any("plugins" in err for err in result.errors)

    def test_invalid_missing_git(self, tmp_path: Path) -> None:
        """Verify ATK Home without .git reports specific error."""
        # Given
        atk_home = tmp_path / ".atk"
        atk_home.mkdir()
        (atk_home / "manifest.yaml").touch()
        (atk_home / "plugins").mkdir()
        # Note: .git is missing

        # When
        result = validate_atk_home(atk_home)

        # Then
        assert result.is_valid is False
        assert any(".git" in err or "git" in err.lower() for err in result.errors)

    def test_invalid_nonexistent_directory(self, tmp_path: Path) -> None:
        """Verify nonexistent directory reports specific error."""
        # Given
        nonexistent = tmp_path / "does-not-exist"

        # When
        result = validate_atk_home(nonexistent)

        # Then
        assert result.is_valid is False
        assert any("does not exist" in err.lower() for err in result.errors)

    def test_invalid_file_instead_of_directory(self, tmp_path: Path) -> None:
        """Verify file (not directory) reports specific error."""
        # Given
        file_path = tmp_path / "not-a-directory"
        file_path.touch()

        # When
        result = validate_atk_home(file_path)

        # Then
        assert result.is_valid is False
        assert any("not a directory" in err.lower() for err in result.errors)

    def test_multiple_missing_components(self, tmp_path: Path) -> None:
        """Verify all missing components are reported."""
        # Given - empty directory
        atk_home = tmp_path / ".atk"
        atk_home.mkdir()
        # Note: manifest.yaml, plugins/, .git all missing

        # When
        result = validate_atk_home(atk_home)

        # Then
        assert result.is_valid is False
        # And - should report all three missing components
        assert len(result.errors) == 3


class TestATKHomeNotInitializedError:
    """Tests for the ATKHomeNotInitializedError exception."""

    def test_exception_message(self) -> None:
        """Verify exception has helpful message."""
        # Given
        path = Path("/some/path")

        # When
        error = ATKHomeNotInitializedError(path)

        # Then
        assert str(path) in str(error)
        assert "not initialized" in str(error).lower()

    def test_exception_stores_path(self) -> None:
        """Verify exception stores the path."""
        # Given
        path = Path("/some/path")

        # When
        error = ATKHomeNotInitializedError(path)

        # Then
        assert error.path == path

