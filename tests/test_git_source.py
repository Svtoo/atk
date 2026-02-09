"""Tests for git source fetch.

Tests fetching plugin files from git repos that follow the .atk/ convention.
"""

from pathlib import Path

import pytest

from atk.git_source import (
    GitPluginNotFoundError,
    GitSourceError,
    fetch_git_plugin,
    normalize_git_url,
)
from tests.conftest import create_fake_git_repo


class TestNormalizeGitUrl:
    """Tests for URL normalization."""

    def test_https_url_unchanged(self) -> None:
        """HTTPS URLs pass through unchanged."""
        url = "https://github.com/org/repo"
        assert normalize_git_url(url) == url

    def test_http_url_unchanged(self) -> None:
        """HTTP URLs pass through unchanged."""
        url = "http://github.com/org/repo"
        assert normalize_git_url(url) == url

    def test_ssh_url_unchanged(self) -> None:
        """SSH URLs pass through unchanged."""
        url = "git@github.com:org/repo.git"
        assert normalize_git_url(url) == url

    def test_shorthand_gets_https_prefix(self) -> None:
        """Shorthand like github.com/org/repo gets https:// prefix."""
        shorthand = "github.com/org/repo"
        expected = "https://github.com/org/repo"
        assert normalize_git_url(shorthand) == expected

    def test_shorthand_with_git_suffix(self) -> None:
        """Shorthand with .git suffix gets https:// prefix."""
        shorthand = "gitlab.com/org/repo.git"
        expected = "https://gitlab.com/org/repo.git"
        assert normalize_git_url(shorthand) == expected


class TestFetchGitPlugin:
    """Tests for fetching a plugin from a git repo with .atk/ directory."""

    def test_fetches_atk_dir_contents(self, tmp_path: Path) -> None:
        """Fetch copies .atk/ contents to target directory."""
        # Given
        repo = create_fake_git_repo(tmp_path)
        target_dir = tmp_path / "target"

        # When
        result = fetch_git_plugin(url=repo.url, target_dir=target_dir, ref=repo.commit_hash)

        # Then — plugin files are copied
        assert target_dir.exists()
        assert (target_dir / "plugin.yaml").exists()
        assert (target_dir / "install.sh").exists()
        assert result.commit_hash == repo.commit_hash

    def test_returns_full_commit_hash(self, tmp_path: Path) -> None:
        """Fetch returns the full 40-char commit hash for version pinning."""
        # Given
        repo = create_fake_git_repo(tmp_path)
        target_dir = tmp_path / "target"

        # When
        result = fetch_git_plugin(url=repo.url, target_dir=target_dir, ref=repo.commit_hash)

        # Then
        assert result.commit_hash == repo.commit_hash

    def test_missing_atk_dir_raises(self, tmp_path: Path) -> None:
        """Fetch raises GitPluginNotFoundError when repo has no .atk/ dir."""
        # Given
        repo = create_fake_git_repo(tmp_path, include_atk_dir=False)
        target_dir = tmp_path / "target"

        # When/Then
        with pytest.raises(GitPluginNotFoundError, match=".atk/"):
            fetch_git_plugin(url=repo.url, target_dir=target_dir, ref=repo.commit_hash)

    def test_missing_plugin_yaml_raises(self, tmp_path: Path) -> None:
        """Fetch raises GitPluginNotFoundError when .atk/ has no plugin.yaml."""
        # Given
        repo = create_fake_git_repo(tmp_path, include_plugin_yaml=False)
        target_dir = tmp_path / "target"

        # When/Then
        with pytest.raises(GitPluginNotFoundError, match="plugin.yaml"):
            fetch_git_plugin(url=repo.url, target_dir=target_dir, ref=repo.commit_hash)

    def test_invalid_url_raises(self, tmp_path: Path) -> None:
        """Fetch raises GitSourceError when URL is unreachable."""
        # Given
        target_dir = tmp_path / "target"

        # When/Then
        with pytest.raises(GitSourceError):
            fetch_git_plugin(
                url="https://nonexistent.invalid/repo",
                target_dir=target_dir,
                ref="deadbeef" * 5,
            )

