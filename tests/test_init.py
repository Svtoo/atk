"""Tests for atk init command."""

import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.init import init_atk_home
from atk.manifest_schema import ManifestSchema


class TestInitAtkHome:
    """Tests for init_atk_home function."""

    def test_creates_directory_structure(self, tmp_path: Path) -> None:
        """Verify init creates all required directories and files."""
        # Given
        target = tmp_path / ".atk"

        # When
        result = init_atk_home(target)

        # Then - directory structure created
        assert result.is_valid is True
        assert target.is_dir()
        assert (target / "manifest.yaml").is_file()
        assert (target / "plugins").is_dir()
        assert (target / ".gitignore").is_file()
        assert (target / ".git").is_dir()

    def test_manifest_has_correct_content(self, tmp_path: Path) -> None:
        """Verify manifest.yaml has correct initial content."""
        # Given
        target = tmp_path / ".atk"

        # When
        init_atk_home(target)

        # Then - deserialize and validate as Pydantic model
        manifest_content = (target / "manifest.yaml").read_text()
        manifest_data = yaml.safe_load(manifest_content)
        manifest = ManifestSchema(**manifest_data)

        assert manifest.schema_version is not None
        assert manifest.config.auto_commit is True
        assert manifest.plugins == []

    def test_gitignore_excludes_env_files(self, tmp_path: Path) -> None:
        """Verify .gitignore contains *.env pattern."""
        # Given
        target = tmp_path / ".atk"

        # When
        init_atk_home(target)

        # Then
        gitignore_content = (target / ".gitignore").read_text()
        assert "*.env" in gitignore_content
        assert ".env.*" in gitignore_content
        assert "plugins/" in gitignore_content

    def test_git_repo_initialized_with_commit(self, tmp_path: Path) -> None:
        """Verify git repo is initialized with initial commit."""
        # Given
        target = tmp_path / ".atk"

        # When
        init_atk_home(target)

        # Then - check git log has initial commit
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=target,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "Initialize ATK Home" in result.stdout

    def test_git_commit_uses_atk_author(self, tmp_path: Path) -> None:
        """Verify git commit uses ATK as author (from git module)."""
        # Given
        target = tmp_path / ".atk"

        # When
        init_atk_home(target)

        # Then - check git log shows ATK as author
        result = subprocess.run(
            ["git", "log", "--format=%an <%ae>", "-1"],
            cwd=target,
            capture_output=True,
            text=True,
            check=True,
        )
        expected_author = "ATK <atk@localhost>"
        assert result.stdout.strip() == expected_author

    def test_idempotent_when_already_initialized(self, tmp_path: Path) -> None:
        """Verify init is no-op when ATK Home already valid."""
        # Given - already initialized
        target = tmp_path / ".atk"
        init_atk_home(target)
        original_manifest = (target / "manifest.yaml").read_text()

        # When - init again
        result = init_atk_home(target)

        # Then - still valid, content unchanged
        assert result.is_valid is True
        assert (target / "manifest.yaml").read_text() == original_manifest

    def test_fails_if_path_exists_but_invalid(self, tmp_path: Path) -> None:
        """Verify init fails if directory exists but is not valid ATK Home."""
        # Given - directory with some random content
        target = tmp_path / ".atk"
        target.mkdir()
        (target / "random-file.txt").write_text("not an atk home")

        # When
        result = init_atk_home(target)

        # Then
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_fails_if_path_is_file(self, tmp_path: Path) -> None:
        """Verify init fails if path is a file, not directory."""
        # Given
        target = tmp_path / ".atk"
        target.touch()

        # When
        result = init_atk_home(target)

        # Then
        assert result.is_valid is False
        assert any("file" in err.lower() for err in result.errors)

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Verify init creates parent directories if needed."""
        # Given
        target = tmp_path / "deep" / "nested" / ".atk"

        # When
        result = init_atk_home(target)

        # Then
        assert result.is_valid is True
        assert target.is_dir()


class TestInitCLI:
    """Tests for atk init CLI command."""

    @pytest.fixture(autouse=True)
    def setup_runner(self) -> None:
        """Set up CLI test runner."""
        self.runner = CliRunner()

    def test_init_default_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify atk init uses ATK_HOME when set."""
        # Given
        atk_home = tmp_path / ".atk"
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = self.runner.invoke(app, ["init"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert atk_home.is_dir()
        assert (atk_home / "manifest.yaml").is_file()

    def test_init_custom_path(self, tmp_path: Path) -> None:
        """Verify atk init with custom path argument."""
        # Given
        custom_path = tmp_path / "my-atk"

        # When
        result = self.runner.invoke(app, ["init", str(custom_path)])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert custom_path.is_dir()
        assert (custom_path / "manifest.yaml").is_file()

    def test_init_already_initialized(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify atk init is idempotent."""
        # Given - already initialized
        atk_home = tmp_path / ".atk"
        monkeypatch.setenv("ATK_HOME", str(atk_home))
        self.runner.invoke(app, ["init"])

        # When - init again
        result = self.runner.invoke(app, ["init"])

        # Then - still success
        assert result.exit_code == exit_codes.SUCCESS

    def test_init_fails_on_invalid_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify atk init fails if directory exists but invalid."""
        # Given - directory with random content
        atk_home = tmp_path / ".atk"
        atk_home.mkdir()
        (atk_home / "random.txt").write_text("not atk")
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = self.runner.invoke(app, ["init"])

        # Then
        assert result.exit_code == exit_codes.GENERAL_ERROR

