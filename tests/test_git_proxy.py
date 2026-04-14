"""Tests for atk git proxy command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.git import has_remote
from atk.init import init_atk_home

runner = CliRunner()


class TestGitProxy:
    """Tests for atk git proxy command."""

    def test_git_proxy_exits_zero_on_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk git exits 0 when git command succeeds."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["git", "rev-parse", "--git-dir"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS

    def test_git_proxy_passes_exit_code_on_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk git returns git's exit code on failure."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When — invalid git subcommand
        result = runner.invoke(app, ["git", "not-a-real-command"])

        # Then — git exits non-zero
        assert result.exit_code != exit_codes.SUCCESS

    def test_git_proxy_requires_initialized_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk git fails when ATK Home is not initialized."""
        # Given
        atk_home = tmp_path / ".atk"
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["git", "status"])

        # Then
        assert result.exit_code == exit_codes.HOME_NOT_INITIALIZED

    def test_git_proxy_remote_add(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify atk git remote add actually adds a remote to .atk repo."""
        # Given
        atk_home = tmp_path / ".atk"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))
        remote_url = f"file://{tmp_path}/bare.git"

        # When
        result = runner.invoke(app, ["git", "remote", "add", "origin", remote_url])

        # Then — command succeeded
        assert result.exit_code == exit_codes.SUCCESS

        # Verify remote was added by checking git directly
        assert has_remote(atk_home) is True
