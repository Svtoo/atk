"""Git operations for ATK.

Provides functions for git repository management used by ATK Home.
"""

import os
import subprocess
from pathlib import Path


def git_init(path: Path) -> None:
    """Initialize a git repository.

    Args:
        path: Directory to initialize as git repository.

    Raises:
        subprocess.CalledProcessError: If git init fails.
    """
    subprocess.run(
        ["git", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def is_git_repo(path: Path) -> bool:
    """Check if a directory is a git repository.

    Args:
        path: Directory to check.

    Returns:
        True if path is a git repository, False otherwise.
    """
    if not path.exists():
        return False

    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=path,
        capture_output=True,
    )
    return result.returncode == 0


def git_add(path: Path, files: list[str] | None = None) -> None:
    """Stage files for commit.

    Args:
        path: Git repository path.
        files: List of file paths to stage. If None, stages all changes.

    Raises:
        subprocess.CalledProcessError: If git add fails.
    """
    cmd = ["git", "add", "-A"] if files is None else ["git", "add", *files]

    subprocess.run(
        cmd,
        cwd=path,
        check=True,
        capture_output=True,
    )


def has_staged_changes(path: Path) -> bool:
    """Check if there are any staged changes ready to commit.

    Args:
        path: Git repository path.

    Returns:
        True if there are staged changes, False otherwise.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=path,
        capture_output=True,
    )
    # Exit code 1 means there are differences (staged changes exist)
    return result.returncode == 1


def git_commit(path: Path, message: str) -> bool:
    """Create a commit with the given message.

    Uses ATK as the author/committer to avoid requiring user git config.
    Only commits if there are staged changes.

    Args:
        path: Git repository path.
        message: Commit message.

    Returns:
        True if a commit was created, False if there were no changes to commit.

    Raises:
        subprocess.CalledProcessError: If git commit fails for reasons other than
            "nothing to commit".
    """
    # Check if there are any staged changes first
    if not has_staged_changes(path):
        return False

    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "ATK",
            "GIT_AUTHOR_EMAIL": "atk@localhost",
            "GIT_COMMITTER_NAME": "ATK",
            "GIT_COMMITTER_EMAIL": "atk@localhost",
        },
    )
    return True

