"""Tests for source resolution.

Determines whether user input to `atk add` is a local path, git URL, or registry name.
"""

from pathlib import Path

import pytest

from atk.manifest_schema import SourceType
from atk.source import resolve_source


class TestResolveSourceLocal:
    """Local path detection: if the path exists on disk, it's local."""

    def test_existing_directory_is_local(self, tmp_path: Path) -> None:
        """A path that exists as a directory resolves to local."""
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.yaml").write_text("name: test")

        result = resolve_source(str(plugin_dir))

        assert result.source_type == SourceType.LOCAL
        assert result.path == plugin_dir

    def test_existing_file_is_local(self, tmp_path: Path) -> None:
        """A path that exists as a file resolves to local."""
        plugin_file = tmp_path / "my-plugin.yaml"
        plugin_file.write_text("name: test")

        result = resolve_source(str(plugin_file))

        assert result.source_type == SourceType.LOCAL
        assert result.path == plugin_file

    def test_relative_path_with_dot_slash_is_local(self) -> None:
        """./some-dir is always treated as local, even if it doesn't exist."""
        result = resolve_source("./my-plugin")

        assert result.source_type == SourceType.LOCAL

    def test_relative_path_with_dot_dot_is_local(self) -> None:
        """../some-dir is always treated as local."""
        result = resolve_source("../my-plugin")

        assert result.source_type == SourceType.LOCAL

    def test_absolute_path_is_local(self) -> None:
        """/some/absolute/path is always treated as local."""
        result = resolve_source("/tmp/my-plugin")

        assert result.source_type == SourceType.LOCAL

    def test_tilde_path_is_local(self) -> None:
        """~/some-dir is always treated as local."""
        result = resolve_source("~/my-plugin")

        assert result.source_type == SourceType.LOCAL


class TestResolveSourceGit:
    """Git URL detection: various URL formats."""

    def test_https_github_url(self) -> None:
        url = "https://github.com/org/repo"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url

    def test_https_github_url_with_git_suffix(self) -> None:
        url = "https://github.com/org/repo.git"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url

    def test_ssh_git_url(self) -> None:
        url = "git@github.com:org/repo.git"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url

    def test_shorthand_github_url(self) -> None:
        """github.com/org/repo (no scheme) is a git URL."""
        url = "github.com/org/repo"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url

    def test_https_gitlab_url(self) -> None:
        url = "https://gitlab.com/org/repo"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url

    def test_shorthand_gitlab_url(self) -> None:
        url = "gitlab.com/org/repo"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url

    def test_generic_https_git_url(self) -> None:
        """Any https URL with a path is treated as git."""
        url = "https://my-server.com/org/repo"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url


    def test_file_url_is_git(self) -> None:
        """file:// URLs are treated as git (used for local repo testing)."""
        url = "file:///tmp/some-repo"
        result = resolve_source(url)

        assert result.source_type == SourceType.GIT
        assert result.url == url


class TestResolveSourceRegistry:
    """Registry name detection: bare names without path separators or URL patterns."""

    def test_simple_name(self) -> None:
        result = resolve_source("openmemory")

        assert result.source_type == SourceType.REGISTRY
        assert result.name == "openmemory"

    def test_hyphenated_name(self) -> None:
        result = resolve_source("piper-tts")

        assert result.source_type == SourceType.REGISTRY
        assert result.name == "piper-tts"

    def test_name_with_numbers(self) -> None:
        result = resolve_source("tool2")

        assert result.source_type == SourceType.REGISTRY
        assert result.name == "tool2"


class TestResolveSourceEdgeCases:
    """Edge cases and ambiguous inputs."""

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            resolve_source("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            resolve_source("   ")

    def test_name_that_looks_like_path_but_doesnt_exist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A bare name like 'openmemory' that doesn't exist on disk is registry, not local."""
        monkeypatch.chdir(tmp_path)

        result = resolve_source("openmemory")

        assert result.source_type == SourceType.REGISTRY

