"""Source resolution for plugin add (Phase 4.1).

Determines whether user input to `atk add` is a local path, git URL,
or registry name.

Resolution order:
1. Explicit path indicators (./  ../  /  ~/) → local
2. Path exists on disk → local
3. Matches URL pattern → git
4. Otherwise → registry name
"""

from dataclasses import dataclass
from pathlib import Path

from atk.manifest_schema import SourceType


@dataclass(frozen=True)
class ResolvedSource:
    """Result of source resolution.

    Exactly one of path, url, or name is set depending on source_type.
    """

    source_type: SourceType

    # LOCAL: filesystem path
    path: Path | None = None

    # GIT: the URL string as provided by the user
    url: str | None = None

    # REGISTRY: bare plugin name
    name: str | None = None


def _is_explicit_path(source: str) -> bool:
    """Check if the source string is syntactically a filesystem path.

    These indicators mean "local" regardless of whether the path exists:
    - Starts with ./  or  ../  (relative)
    - Starts with /  (absolute)
    - Starts with ~  (home directory)
    """
    return source.startswith(("./", "../", "/", "~/", "~\\"))


def _is_git_url(source: str) -> bool:
    """Check if the source string looks like a git URL.

    Recognized patterns:
    - https://host/org/repo[.git]
    - git@host:org/repo[.git]
    - host.tld/org/repo  (shorthand, e.g. github.com/org/repo)
    """
    # SSH URLs: git@host:path
    if source.startswith("git@") and ":" in source[4:]:
        return True

    # HTTPS URLs
    if source.startswith(("https://", "http://")):
        return True

    # Shorthand: contains a dot before the first slash (domain.tld/path)
    # e.g. github.com/org/repo, gitlab.com/org/repo
    if "/" in source:
        host_part = source.split("/", 1)[0]
        if "." in host_part:
            return True

    return False


def resolve_source(source: str) -> ResolvedSource:
    """Classify user input as local path, git URL, or registry name.

    Args:
        source: Raw string from `atk add <source>`.

    Returns:
        ResolvedSource with the classification and parsed details.

    Raises:
        ValueError: If source is empty or whitespace-only.
    """
    source = source.strip()
    if not source:
        msg = "Source cannot be empty"
        raise ValueError(msg)

    # 1. Explicit path syntax → local (even if path doesn't exist)
    if _is_explicit_path(source):
        return ResolvedSource(
            source_type=SourceType.LOCAL,
            path=Path(source),
        )

    # 2. Path exists on disk → local
    candidate = Path(source)
    if candidate.exists():
        return ResolvedSource(
            source_type=SourceType.LOCAL,
            path=candidate,
        )

    # 3. URL pattern → git
    if _is_git_url(source):
        return ResolvedSource(
            source_type=SourceType.GIT,
            url=source,
        )

    # 4. Everything else → registry name
    return ResolvedSource(
        source_type=SourceType.REGISTRY,
        name=source,
    )

