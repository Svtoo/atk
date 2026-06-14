"""Tests for the `atk doctor` migration command."""

import subprocess
from pathlib import Path

from atk.commands.doctor import run_doctor
from atk.git import git_add, git_commit, list_tracked_secrets
from atk.init import init_atk_home


def _make_leaky_home(tmp_path: Path) -> tuple[Path, Path]:
    """Build an ATK Home in the pre-fix broken state: a plugin exemption
    appended AFTER the secret rule, and a committed plugin .env."""
    atk_home = tmp_path / "atk-home"
    init_atk_home(atk_home)
    gitignore = atk_home / ".gitignore"
    # Append the exemption after the (now-last) secret block — the bug.
    gitignore.write_text(gitignore.read_text() + "!plugins/leaky/\n!plugins/leaky/**\n")
    env_file = atk_home / "plugins" / "leaky" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("API_KEY=secret\n")
    # With the broken ordering, git add -A stages the .env (it's re-included).
    git_add(atk_home)
    git_commit(atk_home, "leak a secret by mistake")
    return atk_home, env_file


def _is_ignored(atk_home: Path, rel: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", rel], cwd=atk_home, capture_output=True
    )
    return result.returncode == 0


class TestRunDoctor:
    def test_untracks_leaked_secret_and_fixes_gitignore(self, tmp_path: Path) -> None:
        """A committed plugin .env is untracked (kept on disk), the gitignore is
        re-ordered, and the repair is committed when auto_commit is on."""
        # Given
        atk_home, env_file = _make_leaky_home(tmp_path)
        assert "plugins/leaky/.env" in list_tracked_secrets(atk_home)

        # When
        result = run_doctor(atk_home, auto_commit=True)

        # Then
        assert result.gitignore_fixed is True
        assert "plugins/leaky/.env" in result.untracked_secrets
        assert result.committed is True
        assert list_tracked_secrets(atk_home) == []
        assert env_file.exists()  # kept on disk
        assert _is_ignored(atk_home, "plugins/leaky/.env")

    def test_healthy_home_is_noop(self, tmp_path: Path) -> None:
        """A freshly-initialised home needs no repair."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # When
        result = run_doctor(atk_home, auto_commit=True)

        # Then
        assert result.gitignore_fixed is False
        assert result.untracked_secrets == []
        assert result.committed is False

    def test_respects_auto_commit_false(self, tmp_path: Path) -> None:
        """With auto_commit off, the repair is applied but not committed."""
        # Given
        atk_home, _ = _make_leaky_home(tmp_path)

        # When
        result = run_doctor(atk_home, auto_commit=False)

        # Then
        assert result.gitignore_fixed is True
        assert "plugins/leaky/.env" in result.untracked_secrets
        assert result.committed is False
        # The fix is on disk even though it isn't committed.
        assert _is_ignored(atk_home, "plugins/leaky/.env")
