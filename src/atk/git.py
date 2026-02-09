"""Git operations for ATK.

Provides functions for git repository management used by ATK Home.
"""

import os
import subprocess
from pathlib import Path


def is_git_available() -> bool:
    """Check if git command is available on the system.

    Returns:
        True if git is available, False otherwise.
    """
    try:
        subprocess.run(
            ["git", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except FileNotFoundError:
        return False


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


def add_gitignore_exemption(path: Path, plugin_dir: str) -> None:
    """Add gitignore exemption for a local plugin.

    Adds two lines to .gitignore to track a local plugin:
    - !plugins/<plugin_dir>/
    - !plugins/<plugin_dir>/**

    This function is idempotent - if the exemption already exists, it won't be duplicated.

    Args:
        path: Path to directory containing .gitignore (typically ATK Home root).
        plugin_dir: Plugin directory name (e.g., "my-plugin").

    Raises:
        FileNotFoundError: If .gitignore does not exist (ATK Home not properly initialized).
    """
    gitignore_path = path / ".gitignore"

    if not gitignore_path.exists():
        msg = f".gitignore not found at {gitignore_path}. ATK Home may not be properly initialized."
        raise FileNotFoundError(msg)

    content = gitignore_path.read_text()

    # Generate exemption lines
    exemption_dir = f"!plugins/{plugin_dir}/"
    exemption_glob = f"!plugins/{plugin_dir}/**"

    # Check if exemptions already exist (idempotent)
    lines = content.split("\n") if content else []
    if exemption_dir in lines and exemption_glob in lines:
        return  # Already exists, nothing to do

    # Add exemptions at the end
    if content and not content.endswith("\n"):
        content += "\n"

    content += f"{exemption_dir}\n{exemption_glob}\n"

    # Write back
    gitignore_path.write_text(content)


def remove_gitignore_exemption(path: Path, plugin_dir: str) -> None:
    """Remove gitignore exemption for a local plugin.

    Removes the two exemption lines added by add_gitignore_exemption:
    - !plugins/<plugin_dir>/
    - !plugins/<plugin_dir>/**

    This function is idempotent - if the exemption doesn't exist, it's a no-op.

    Args:
        path: Path to directory containing .gitignore (typically ATK Home root).
        plugin_dir: Plugin directory name (e.g., "my-plugin").

    Raises:
        FileNotFoundError: If .gitignore does not exist (ATK Home not properly initialized).
    """
    gitignore_path = path / ".gitignore"

    if not gitignore_path.exists():
        msg = f".gitignore not found at {gitignore_path}. ATK Home may not be properly initialized."
        raise FileNotFoundError(msg)

    content = gitignore_path.read_text()

    # Generate exemption lines to remove
    exemption_dir = f"!plugins/{plugin_dir}/"
    exemption_glob = f"!plugins/{plugin_dir}/**"

    # Filter out the exemption lines
    lines = content.split("\n")
    filtered_lines = [
        line for line in lines if line not in (exemption_dir, exemption_glob)
    ]

    # Write back
    gitignore_path.write_text("\n".join(filtered_lines))



def git_ls_remote(url: str) -> str:
    """Get the HEAD commit hash from a remote repository without cloning.

    Uses ``git ls-remote`` which only contacts the remote for ref info,
    making it much cheaper than a full clone or fetch.

    Args:
        url: Git URL of the remote repository.

    Returns:
        The full 40-char commit hash of the remote HEAD.

    Raises:
        subprocess.CalledProcessError: If the remote is unreachable or git fails.
        ValueError: If the remote has no HEAD ref.
    """
    result = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    # Output format: "<hash>\tHEAD\n"
    output = result.stdout.strip()
    if not output:
        msg = f"Remote '{url}' returned no HEAD ref"
        raise ValueError(msg)
    commit_hash = output.split("\t")[0]
    return commit_hash


ATK_REF_FILE = ".atk-ref"


def write_atk_ref(plugin_dir: Path, commit_hash: str) -> None:
    """Write the commit hash to the .atk-ref file in a plugin directory.

    This records which commit the on-disk plugin files correspond to,
    enabling upgrade checks without a full fetch.

    Args:
        plugin_dir: Path to the plugin directory.
        commit_hash: The commit hash to record.
    """
    ref_path = plugin_dir / ATK_REF_FILE
    ref_path.write_text(commit_hash + "\n")


def read_atk_ref(plugin_dir: Path) -> str | None:
    """Read the commit hash from the .atk-ref file in a plugin directory.

    Args:
        plugin_dir: Path to the plugin directory.

    Returns:
        The commit hash string, or None if the file does not exist.
    """
    ref_path = plugin_dir / ATK_REF_FILE
    if not ref_path.exists():
        return None
    return ref_path.read_text().strip()


def sparse_clone(url: str, clone_dir: Path, ref: str) -> None:
    """Clone a repo at a specific ref with blob filtering and sparse checkout enabled.

    Clones with --filter=blob:none (fetches commit graph but no file content),
    then checks out the requested ref before any sparse_checkout materializes blobs.

    Args:
        url: Git URL to clone.
        clone_dir: Target directory for the clone.
        ref: Commit hash to check out after cloning.

    Raises:
        subprocess.CalledProcessError: If git clone or checkout fails.
    """
    subprocess.run(
        ["git", "clone", "--filter=blob:none", "--sparse", url, str(clone_dir)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "checkout", ref],
        cwd=clone_dir,
        check=True,
        capture_output=True,
    )


def sparse_checkout(clone_dir: Path, patterns: list[str]) -> None:
    """Set sparse-checkout patterns in non-cone mode.

    Args:
        clone_dir: Path to the cloned repo.
        patterns: Sparse checkout patterns (e.g. ["/index.yaml"]).

    Raises:
        subprocess.CalledProcessError: If git sparse-checkout fails.
    """
    subprocess.run(
        ["git", "sparse-checkout", "set", "--no-cone", *patterns],
        cwd=clone_dir,
        check=True,
        capture_output=True,
    )


def get_commit_hash(clone_dir: Path) -> str:
    """Get the HEAD commit hash from a git repo.

    Args:
        clone_dir: Path to the git repo.

    Returns:
        The full 40-char commit hash.

    Raises:
        subprocess.CalledProcessError: If git rev-parse fails.
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=clone_dir,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
