"""Git source fetch operations for ATK.

Fetches plugins from arbitrary git repositories that follow the .atk/ convention.
Third-party repos provide an ATK plugin via a .atk/ directory at repo root.
ATK sparse-clones the repo, checks out only .atk/, copies its contents to the
target plugin directory, and returns the commit hash for version pinning.
"""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from atk.git import get_commit_hash, sparse_checkout, sparse_clone

ATK_DIR = ".atk"


class GitSourceError(Exception):
    """Raised when fetching from a git source fails."""


class GitPluginNotFoundError(Exception):
    """Raised when the repo does not contain an .atk/ directory."""


@dataclass
class GitFetchResult:
    """Result of fetching a plugin from a git source."""

    commit_hash: str


def normalize_git_url(url: str) -> str:
    """Normalize a user-provided URL into a form git can clone.

    Shorthand like ``github.com/org/repo`` becomes ``https://github.com/org/repo``.
    URLs that already have a scheme or use SSH syntax are returned unchanged.

    Args:
        url: Raw URL string from source resolution.

    Returns:
        A URL suitable for ``git clone``.
    """
    # SSH: git@host:path — already valid
    if url.startswith("git@"):
        return url

    # Already has a scheme
    if url.startswith(("https://", "http://", "file://")):
        return url

    # Shorthand: host.tld/org/repo → https://host.tld/org/repo
    return f"https://{url}"


def fetch_git_plugin(
    url: str,
    target_dir: Path,
) -> GitFetchResult:
    """Fetch a plugin from a git repo that follows the .atk/ convention.

    Sparse-clones the repo (no blobs), checks out only the ``.atk/`` directory,
    copies its contents to *target_dir*, and returns the commit hash.

    Args:
        url: Git URL (may be shorthand — will be normalized).
        target_dir: Where to copy the plugin files.

    Returns:
        GitFetchResult with the commit hash of the repo HEAD.

    Raises:
        GitPluginNotFoundError: If the repo has no ``.atk/`` directory.
        GitSourceError: If the clone or checkout fails.
    """
    clone_url = normalize_git_url(url)

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "repo"

        try:
            sparse_clone(clone_url, clone_dir)
            sparse_checkout(clone_dir, [f"/{ATK_DIR}"])
        except subprocess.CalledProcessError as e:
            msg = f"Failed to fetch from {clone_url}: {e.stderr.decode()}"
            raise GitSourceError(msg) from e

        atk_dir = clone_dir / ATK_DIR
        if not atk_dir.is_dir():
            msg = f"Repository does not contain an '{ATK_DIR}/' directory"
            raise GitPluginNotFoundError(msg)

        plugin_yaml = atk_dir / "plugin.yaml"
        if not plugin_yaml.exists():
            msg = f"'{ATK_DIR}/' directory does not contain plugin.yaml"
            raise GitPluginNotFoundError(msg)

        commit_hash = get_commit_hash(clone_dir)

        # Copy .atk/ contents (not the .atk/ dir itself) to target_dir
        shutil.copytree(atk_dir, target_dir)

        return GitFetchResult(commit_hash=commit_hash)

