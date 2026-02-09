"""Shared plugin fetch operations for ATK.

Dispatches to the correct fetcher (registry or git) based on source type.
Used by both upgrade and bootstrap flows.
"""

from pathlib import Path

import atk.registry as registry_mod
from atk.git_source import fetch_git_plugin
from atk.manifest_schema import SourceType


class FetchError(Exception):
    """Raised when fetching a plugin from its source fails."""


def fetch_plugin_source(
    source_type: SourceType,
    directory: str,
    target_dir: Path,
    ref: str,
    source_url: str | None = None,
) -> str:
    """Fetch plugin files from a remote source into target_dir.

    For registry plugins, *directory* is used as the registry slug name.
    For git plugins, *source_url* must be provided.

    Args:
        source_type: Whether the plugin comes from registry or git.
        directory: Plugin directory name (registry slug for registry sources).
        target_dir: Where to write the fetched files.
        ref: Commit hash to check out.
        source_url: Git URL (required for git sources, ignored for registry).

    Returns:
        The commit hash of the fetched version.

    Raises:
        FetchError: If source_url is missing for a git source.
        ValueError: If source_type is LOCAL (local plugins cannot be fetched).
    """
    if source_type == SourceType.LOCAL:
        msg = "Local plugins cannot be fetched from a remote source"
        raise ValueError(msg)

    if source_type == SourceType.REGISTRY:
        result = registry_mod.fetch_registry_plugin(name=directory, target_dir=target_dir, ref=ref,)
        return result.commit_hash

    if not source_url:
        msg = f"Git plugin '{directory}' has no source URL in manifest"
        raise FetchError(msg)

    result = fetch_git_plugin(url=source_url, target_dir=target_dir, ref=ref)
    return result.commit_hash

