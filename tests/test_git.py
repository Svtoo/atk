"""Tests for git operations module."""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from atk.git import (
    ATK_REF_FILE,
    add_gitignore_exemption,
    git_add,
    git_commit,
    git_init,
    git_ls_remote,
    has_staged_changes,
    is_git_available,
    is_git_repo,
    read_atk_ref,
    remove_gitignore_exemption,
    write_atk_ref,
)


class TestGitInit:
    """Tests for git_init function."""

    def test_initializes_git_repo(self, tmp_path: Path) -> None:
        """Verify git_init creates a .git directory."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # When
        git_init(repo_path)

        # Then
        assert (repo_path / ".git").is_dir()

    def test_raises_on_nonexistent_path(self, tmp_path: Path) -> None:
        """Verify git_init raises for nonexistent path."""
        # Given
        nonexistent = tmp_path / "does-not-exist"

        # When/Then - subprocess raises FileNotFoundError for missing cwd
        with pytest.raises(FileNotFoundError):
            git_init(nonexistent)


class TestIsGitRepo:
    """Tests for is_git_repo function."""

    def test_returns_true_for_git_repo(self, tmp_path: Path) -> None:
        """Verify is_git_repo returns True for initialized repo."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)

        # When
        result = is_git_repo(repo_path)

        # Then
        assert result is True

    def test_returns_false_for_non_repo(self, tmp_path: Path) -> None:
        """Verify is_git_repo returns False for regular directory."""
        # Given
        regular_dir = tmp_path / "not-a-repo"
        regular_dir.mkdir()

        # When
        result = is_git_repo(regular_dir)

        # Then
        assert result is False

    def test_returns_false_for_nonexistent_path(self, tmp_path: Path) -> None:
        """Verify is_git_repo returns False for nonexistent path."""
        # Given
        nonexistent = tmp_path / "does-not-exist"

        # When
        result = is_git_repo(nonexistent)

        # Then
        assert result is False


class TestGitAdd:
    """Tests for git_add function."""

    def test_stages_single_file(self, tmp_path: Path) -> None:
        """Verify git_add stages a single file."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)
        test_file = repo_path / "test.txt"
        test_file.write_text("content")

        # When
        git_add(repo_path, ["test.txt"])

        # Then - file is staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "test.txt" in result.stdout

    def test_stages_all_files(self, tmp_path: Path) -> None:
        """Verify git_add with no files stages all changes."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)
        (repo_path / "file1.txt").write_text("content1")
        (repo_path / "file2.txt").write_text("content2")

        # When - no files specified means stage all
        git_add(repo_path)

        # Then - both files are staged
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "file1.txt" in result.stdout
        assert "file2.txt" in result.stdout


class TestGitCommit:
    """Tests for git_commit function."""

    def test_creates_commit(self, tmp_path: Path) -> None:
        """Verify git_commit creates a commit with message."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)
        (repo_path / "test.txt").write_text("content")
        git_add(repo_path)
        commit_message = "Test commit message"

        # When
        git_commit(repo_path, commit_message)

        # Then - commit exists with correct message
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        assert commit_message in result.stdout

    def test_returns_false_when_nothing_to_commit(self, tmp_path: Path) -> None:
        """Verify git_commit returns False when no staged changes."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)
        (repo_path / "test.txt").write_text("content")
        git_add(repo_path)
        git_commit(repo_path, "Initial commit")
        # No new changes

        # When
        result = git_commit(repo_path, "Should not create this commit")

        # Then
        assert result is False


class TestHasStagedChanges:
    """Tests for has_staged_changes function."""

    def test_returns_true_when_changes_staged(self, tmp_path: Path) -> None:
        """Verify has_staged_changes returns True when files are staged."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)
        (repo_path / "test.txt").write_text("content")
        git_add(repo_path)

        # When
        result = has_staged_changes(repo_path)

        # Then
        assert result is True

    def test_returns_false_when_no_changes_staged(self, tmp_path: Path) -> None:
        """Verify has_staged_changes returns False when nothing is staged."""
        # Given
        repo_path = tmp_path / "repo"
        repo_path.mkdir()
        git_init(repo_path)
        (repo_path / "test.txt").write_text("content")
        git_add(repo_path)
        git_commit(repo_path, "Initial commit")
        # No new changes

        # When
        result = has_staged_changes(repo_path)

        # Then
        assert result is False


class TestIsGitAvailable:
    """Tests for is_git_available function."""

    def test_returns_true_when_git_available(self) -> None:
        """Verify is_git_available returns True when git command exists."""
        # Given - git is available on the system (test environment assumption)

        # When
        result = is_git_available()

        # Then
        assert result is True

    def test_returns_false_when_git_not_available(self) -> None:
        """Verify is_git_available returns False when git command not found."""
        # Given - mock subprocess to simulate git not found
        with patch("atk.git.subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("git not found")

            # When
            result = is_git_available()

            # Then
            assert result is False



class TestGitLsRemote:
    """Tests for git_ls_remote function."""

    def _create_remote_repo(self, tmp_path: Path) -> tuple[str, str]:
        """Create a local git repo and return (file:// URL, commit hash)."""
        repo_dir = tmp_path / "remote-repo"
        repo_dir.mkdir()
        (repo_dir / "README.md").write_text("# Test\n")

        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
        }
        subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=repo_dir, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial"],
            cwd=repo_dir, check=True, capture_output=True, env=env,
        )
        commit_hash = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_dir, check=True, capture_output=True, text=True,
        ).stdout.strip()

        return f"file://{repo_dir}", commit_hash

    def test_returns_head_commit_hash(self, tmp_path: Path) -> None:
        """Verify git_ls_remote returns the correct HEAD commit hash."""
        # Given
        url, expected_hash = self._create_remote_repo(tmp_path)

        # When
        actual_hash = git_ls_remote(url)

        # Then
        assert actual_hash == expected_hash

    def test_invalid_url_raises(self) -> None:
        """Verify git_ls_remote raises for unreachable URL."""
        # Given
        url = "https://nonexistent.invalid/repo"

        # When/Then
        with pytest.raises(subprocess.CalledProcessError):
            git_ls_remote(url)



class TestAtkRef:
    """Tests for write_atk_ref and read_atk_ref functions."""

    def test_write_and_read_roundtrip(self, tmp_path: Path) -> None:
        """Verify writing and reading .atk-ref produces the same hash."""
        # Given
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        commit_hash = "abc123def456"

        # When
        write_atk_ref(plugin_dir, commit_hash)
        actual = read_atk_ref(plugin_dir)

        # Then
        assert actual == commit_hash

    def test_read_returns_none_when_missing(self, tmp_path: Path) -> None:
        """Verify read_atk_ref returns None when .atk-ref does not exist."""
        # Given
        plugin_dir = tmp_path / "no-ref-plugin"
        plugin_dir.mkdir()

        # When
        actual = read_atk_ref(plugin_dir)

        # Then
        assert actual is None

    def test_write_creates_file_with_correct_name(self, tmp_path: Path) -> None:
        """Verify write_atk_ref creates a file named .atk-ref."""
        # Given
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        commit_hash = "deadbeef"

        # When
        write_atk_ref(plugin_dir, commit_hash)

        # Then
        ref_path = plugin_dir / ATK_REF_FILE
        assert ref_path.exists()
        assert ref_path.read_text() == commit_hash + "\n"



class TestAddGitignoreExemption:
    """Tests for add_gitignore_exemption function."""

    def test_adds_exemption_to_existing_gitignore(self, tmp_path: Path) -> None:
        """Verify add_gitignore_exemption adds exemption lines to existing .gitignore."""
        # Given
        gitignore_path = tmp_path / ".gitignore"
        existing_content = "*.env\n.DS_Store\n"
        gitignore_path.write_text(existing_content)
        plugin_dir = "my-plugin"
        exemption_dir = f"!plugins/{plugin_dir}/"
        exemption_glob = f"!plugins/{plugin_dir}/**"
        expected_content = f"{existing_content}{exemption_dir}\n{exemption_glob}\n"

        # When
        add_gitignore_exemption(tmp_path, plugin_dir)

        # Then
        actual_content = gitignore_path.read_text()
        assert actual_content == expected_content

    def test_raises_when_gitignore_missing(self, tmp_path: Path) -> None:
        """Verify add_gitignore_exemption raises FileNotFoundError if .gitignore doesn't exist."""
        # Given
        plugin_dir = "my-plugin"

        # When/Then
        with pytest.raises(FileNotFoundError, match=".gitignore not found"):
            add_gitignore_exemption(tmp_path, plugin_dir)

    def test_is_idempotent(self, tmp_path: Path) -> None:
        """Verify add_gitignore_exemption is idempotent - doesn't duplicate lines."""
        # Given
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("*.env\n")
        plugin_dir = "my-plugin"

        # When - add exemption twice
        add_gitignore_exemption(tmp_path, plugin_dir)
        add_gitignore_exemption(tmp_path, plugin_dir)

        # Then - exemption lines appear only once
        content = gitignore_path.read_text()
        lines = content.split("\n")
        assert lines.count(f"!plugins/{plugin_dir}/") == 1
        assert lines.count(f"!plugins/{plugin_dir}/**") == 1


class TestRemoveGitignoreExemption:
    """Tests for remove_gitignore_exemption function."""

    def test_removes_exemption_from_gitignore(self, tmp_path: Path) -> None:
        """Verify remove_gitignore_exemption removes exemption lines."""
        # Given
        plugin_dir = "my-plugin"
        gitignore_path = tmp_path / ".gitignore"
        exemption_dir = f"!plugins/{plugin_dir}/"
        exemption_glob = f"!plugins/{plugin_dir}/**"
        content = f"*.env\n{exemption_dir}\n{exemption_glob}\n.DS_Store\n"
        gitignore_path.write_text(content)
        expected_content = "*.env\n.DS_Store\n"

        # When
        remove_gitignore_exemption(tmp_path, plugin_dir)

        # Then
        actual_content = gitignore_path.read_text()
        assert actual_content == expected_content

    def test_preserves_other_plugin_exemptions(self, tmp_path: Path) -> None:
        """Verify remove_gitignore_exemption only removes specified plugin's exemption."""
        # Given
        plugin_dir = "my-plugin"
        other_plugin = "other-plugin"
        gitignore_path = tmp_path / ".gitignore"
        exemption_dir = f"!plugins/{plugin_dir}/"
        exemption_glob = f"!plugins/{plugin_dir}/**"
        other_exemption_dir = f"!plugins/{other_plugin}/"
        other_exemption_glob = f"!plugins/{other_plugin}/**"
        content = f"*.env\n{exemption_dir}\n{exemption_glob}\n{other_exemption_dir}\n{other_exemption_glob}\n.DS_Store\n"
        gitignore_path.write_text(content)
        expected_content = f"*.env\n{other_exemption_dir}\n{other_exemption_glob}\n.DS_Store\n"

        # When
        remove_gitignore_exemption(tmp_path, plugin_dir)

        # Then
        actual_content = gitignore_path.read_text()
        assert actual_content == expected_content

    def test_is_idempotent(self, tmp_path: Path) -> None:
        """Verify remove_gitignore_exemption is idempotent - no error if already removed."""
        # Given
        plugin_dir = "my-plugin"
        gitignore_path = tmp_path / ".gitignore"
        gitignore_path.write_text("*.env\n.DS_Store\n")

        # When - remove exemption that doesn't exist
        remove_gitignore_exemption(tmp_path, plugin_dir)

        # Then - no error, file unchanged
        result = gitignore_path.read_text()
        assert result == "*.env\n.DS_Store\n"

    def test_raises_when_gitignore_missing(self, tmp_path: Path) -> None:
        """Verify remove_gitignore_exemption raises FileNotFoundError if .gitignore doesn't exist."""
        # Given
        plugin_dir = "my-plugin"

        # When/Then
        with pytest.raises(FileNotFoundError, match=".gitignore not found"):
            remove_gitignore_exemption(tmp_path, plugin_dir)
