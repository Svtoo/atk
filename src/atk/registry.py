"""Registry fetch operations for ATK.

Fetches plugins from the ATK registry git repo by name.
"""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from atk.registry_schema import RegistryIndexSchema, RegistryPluginEntry

REGISTRY_URL = "https://github.com/Svtoo/atk-registry"


class PluginNotFoundError(Exception):
    """Raised when a plugin name is not found in the registry index."""


class RegistryFetchError(Exception):
    """Raised when fetching from the registry git repo fails."""


@dataclass
class FetchResult:
    """Result of fetching a plugin from the registry."""

    commit_hash: str


def fetch_registry_plugin(
    name: str,
    target_dir: Path,
    registry_url: str | None = None,
) -> FetchResult:
    """Fetch a plugin by name from the registry using sparse checkout.

    Sparse-clones the registry (no blobs), checks out only index.yaml to
    look up the plugin, then checks out only the plugin directory.
    Copies the plugin files to target_dir and returns the commit hash.

    Args:
        name: Plugin name to fetch (e.g., "piper").
        target_dir: Where to copy the plugin files.
        registry_url: Git URL of the registry repo. Defaults to REGISTRY_URL.

    Returns:
        FetchResult with the commit hash of the registry HEAD.

    Raises:
        PluginNotFoundError: If the plugin name is not in the registry index.
        RegistryFetchError: If the clone fails or the plugin directory is missing.
    """
    url = registry_url or REGISTRY_URL
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "registry"

        _sparse_clone(url, clone_dir)

        _sparse_checkout(clone_dir, ["/index.yaml"])

        index_path = clone_dir / "index.yaml"
        if not index_path.exists():
            msg = "Registry does not contain index.yaml"
            raise RegistryFetchError(msg)

        index_data = yaml.safe_load(index_path.read_text())
        index = RegistryIndexSchema.model_validate(index_data)

        entry = _lookup_plugin(index, name)

        _sparse_checkout(clone_dir, [f"/{entry.path}/*"])

        plugin_src = clone_dir / entry.path
        if not plugin_src.is_dir():
            msg = f"Plugin directory '{entry.path}' listed in index but missing from registry"
            raise RegistryFetchError(msg)

        commit_hash = _get_commit_hash(clone_dir)

        shutil.copytree(plugin_src, target_dir)

        return FetchResult(commit_hash=commit_hash)


def _sparse_clone(url: str, clone_dir: Path) -> None:
    """Clone a repo with blob filtering and sparse checkout enabled."""
    try:
        subprocess.run(
            ["git", "clone", "--filter=blob:none", "--sparse", url, str(clone_dir)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        msg = f"Failed to clone registry from {url}: {e.stderr.decode()}"
        raise RegistryFetchError(msg) from e


def _sparse_checkout(clone_dir: Path, patterns: list[str]) -> None:
    """Set sparse-checkout patterns in non-cone mode."""
    try:
        subprocess.run(
            ["git", "sparse-checkout", "set", "--no-cone", *patterns],
            cwd=clone_dir,
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        msg = f"Failed to set sparse checkout: {e.stderr.decode()}"
        raise RegistryFetchError(msg) from e


def _get_commit_hash(clone_dir: Path) -> str:
    """Get the HEAD commit hash from a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        msg = f"Failed to get commit hash: {e.stderr}"
        raise RegistryFetchError(msg) from e


def _lookup_plugin(index: RegistryIndexSchema, name: str) -> RegistryPluginEntry:
    """Find a plugin entry by name in the registry index."""
    for entry in index.plugins:
        if entry.name == name:
            return entry

    msg = f"Plugin '{name}' not found in registry"
    raise PluginNotFoundError(msg)

