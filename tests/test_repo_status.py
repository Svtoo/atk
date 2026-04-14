"""Tests for repository status rendering in atk status."""

import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.init import init_atk_home

runner = CliRunner()


class TestRepoStatusInCli:
    """Tests for repository section in atk status output."""

    def test_status_shows_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk status output includes branch name."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["status"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "Repository:" in result.output
        assert "Branch:" in result.output

    def test_status_shows_no_remote(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk status shows (none) when no remote configured."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["status"])

        # Then
        assert "Remote:" in result.output
        assert "(none)" in result.output

    def test_status_shows_remote_when_configured(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk status shows remote name and URL."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))
        remote_url = f"file://{tmp_path}/bare.git"
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=atk_home, check=True, capture_output=True,
        )

        # When
        result = runner.invoke(app, ["status"])

        # Then
        assert "origin" in result.output
        assert "bare.git" in result.output

    def test_status_shows_last_commit(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk status shows last commit info."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["status"])

        # Then
        assert "Last commit:" in result.output
        assert "Initialize ATK Home" in result.output

    def test_status_shows_clean_working_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk status shows clean working dir."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["status"])

        # Then
        assert "Working dir:" in result.output
        assert "clean" in result.output

    def test_status_shows_dirty_working_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk status shows modified/untracked counts for dirty repo."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))
        # Create an untracked file
        (atk_home / "stray-file.txt").write_text("dirty\n")

        # When
        result = runner.invoke(app, ["status"])

        # Then
        assert "Working dir:" in result.output
        assert "untracked" in result.output
