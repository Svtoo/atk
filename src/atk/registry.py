"""Registry fetch operations for ATK.

Fetches plugins from the ATK registry git repo by name.
"""

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from atk.config import get_registry_url
from atk.errors import format_validation_errors
from atk.git import get_commit_hash, git_ls_remote, sparse_checkout, sparse_clone
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


def _clone_and_load_index(url: str, clone_dir: Path, ref: str) -> RegistryIndexSchema:
    """Sparse-clone the registry and parse index.yaml.

    Clones the registry at the given ref with only index.yaml checked out,
    then parses and validates it. The clone_dir is provided by the caller
    so it can remain alive for subsequent sparse-checkouts in the same session.

    Args:
        url: Git URL of the registry repo.
        clone_dir: Directory to clone into (must not yet exist).
        ref: Commit hash to clone at.

    Returns:
        Parsed RegistryIndexSchema.

    Raises:
        RegistryFetchError: If the clone fails, index.yaml is missing, or
            the schema is invalid.
    """
    try:
        sparse_clone(url, clone_dir, ref)
        sparse_checkout(clone_dir, ["/index.yaml"])
    except subprocess.CalledProcessError as e:
        msg = f"Failed to clone registry from {url}: {e.stderr.decode()}"
        raise RegistryFetchError(msg) from e

    index_path = clone_dir / "index.yaml"
    if not index_path.exists():
        msg = "Registry does not contain index.yaml"
        raise RegistryFetchError(msg)

    index_data = yaml.safe_load(index_path.read_text())
    try:
        return RegistryIndexSchema.model_validate(index_data)
    except ValidationError as e:
        clean_errors = format_validation_errors(e)
        msg = f"Invalid registry index: {clean_errors}"
        raise RegistryFetchError(msg) from e


def fetch_registry_index(atk_home: Path, registry_url: str | None = None) -> RegistryIndexSchema:
    """Fetch and return the parsed registry index.

    Resolves the registry HEAD, sparse-clones only index.yaml, and returns
    the validated index. All network and parse errors are raised as
    RegistryFetchError so callers only need to handle one exception type.

    Args:
        atk_home: Path to ATK Home directory.
        registry_url: Git URL of the registry repo. If not provided, resolves from config.

    Returns:
        Parsed RegistryIndexSchema.

    Raises:
        RegistryFetchError: If the registry is unreachable, clone fails,
            index.yaml is missing, or the index schema is invalid.
    """
    url = registry_url or get_registry_url(atk_home)

    try:
        ref = git_ls_remote(url)
    except (subprocess.CalledProcessError, ValueError) as e:
        msg = f"Failed to reach registry at {url}: {e}"
        raise RegistryFetchError(msg) from e

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "registry"
        return _clone_and_load_index(url, clone_dir, ref)


def fetch_registry_plugin(
    name: str,
    target_dir: Path,
    ref: str,
    atk_home: Path,
    registry_url: str | None = None,
) -> FetchResult:
    """Fetch a plugin by name from the registry using sparse checkout.

    Sparse-clones the registry at the given ref, checks out only index.yaml
    to look up the plugin, then checks out only the plugin directory.
    Copies the plugin files to target_dir and returns the commit hash.

    Args:
        name: Plugin name to fetch (e.g., "piper").
        target_dir: Where to copy the plugin files.
        ref: Commit hash to check out.
        atk_home: Path to ATK Home directory.
        registry_url: Git URL of the registry repo. If not provided, resolves from config.

    Returns:
        FetchResult with the commit hash of the checked-out revision.

    Raises:
        PluginNotFoundError: If the plugin name is not in the registry index.
        RegistryFetchError: If the clone fails or the plugin directory is missing.
    """
    url = registry_url or get_registry_url(atk_home)
    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "registry"

        index = _clone_and_load_index(url, clone_dir, ref)

        entry = _lookup_plugin(index, name)

        try:
            sparse_checkout(clone_dir, [f"/{entry.path}/*"])
        except subprocess.CalledProcessError as e:
            msg = f"Failed to fetch plugin '{name}': {e.stderr.decode()}"
            raise RegistryFetchError(msg) from e

        plugin_src = clone_dir / entry.path
        if not plugin_src.is_dir():
            msg = f"Plugin directory '{entry.path}' listed in index but missing from registry"
            raise RegistryFetchError(msg)

        commit_hash = get_commit_hash(clone_dir)

        shutil.copytree(plugin_src, target_dir)

        return FetchResult(commit_hash=commit_hash)


def _lookup_plugin(index: RegistryIndexSchema, name: str) -> RegistryPluginEntry:
    """Find a plugin entry by name in the registry index."""
    for entry in index.plugins:
        if entry.name == name:
            return entry

    msg = f"Plugin '{name}' not found in registry"
    raise PluginNotFoundError(msg)

