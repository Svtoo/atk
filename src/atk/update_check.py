"""Update check for ATK CLI.

Checks PyPI for newer versions and caches results locally.
Shows a passive notification after CLI command execution.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.request import urlopen

import yaml
from pydantic import BaseModel

# Cache validity period: 6 hours
CACHE_INTERVAL_SECONDS = 6 * 60 * 60

# Cache file name within ATK Home
CACHE_FILENAME = ".update-cache.yaml"

# PyPI package name
PYPI_PACKAGE = "atk-cli"


class UpdateCacheData(BaseModel):
    """Schema for the update check cache file."""

    latest_version: str
    timestamp: float


def _parse_version(version: str) -> tuple[int, ...]:
    """Parse a version string like '1.2.3' into a comparable tuple."""
    return tuple(int(x) for x in version.split("."))


class VersionSource(Protocol):
    """Protocol for fetching the latest version of a package."""

    def fetch_latest(self, package: str) -> str | None:
        """Fetch the latest version string, or None on failure."""
        ...


class PyPIVersionSource:
    """Fetches the latest version from PyPI JSON API."""

    def fetch_latest(self, package: str) -> str | None:
        """Fetch latest version from https://pypi.org/pypi/<package>/json."""
        url = f"https://pypi.org/pypi/{package}/json"
        with urlopen(url, timeout=5) as response:  # noqa: S310
            data = json.loads(response.read())
        version: str = data["info"]["version"]
        return version


@dataclass
class UpdateInfo:
    """Information about an available update."""

    current: str
    latest: str

    def message(self) -> str:
        """Format the update notification message."""
        return f"Update available: {self.current} → {self.latest}\nRun: uv tool upgrade atk-cli"


class UpdateChecker:
    """Checks for updates using a VersionSource with local caching."""

    def __init__(
        self,
        source: VersionSource,
        current_version: str,
        cache_dir: Path,
        cache_interval: int = CACHE_INTERVAL_SECONDS,
    ) -> None:
        self._source = source
        self._current_version = current_version
        self._cache_path = cache_dir / CACHE_FILENAME
        self._cache_interval = cache_interval

    def check(self) -> UpdateInfo | None:
        """Check for updates, using cache when valid.

        Returns UpdateInfo if a newer version is available, None otherwise.
        """
        cached = self._load_cache()
        if cached is not None:
            latest = cached
        else:
            fetched = self._source.fetch_latest(PYPI_PACKAGE)
            if fetched is None:
                return None
            self._save_cache(fetched)
            latest = fetched

        if self._is_newer(latest):
            return UpdateInfo(current=self._current_version, latest=latest)
        return None

    def _is_newer(self, latest: str) -> bool:
        """Compare versions. Returns True if latest > current."""
        return _parse_version(latest) > _parse_version(self._current_version)

    def _load_cache(self) -> str | None:
        """Load cached version if cache exists and is not expired."""
        if not self._cache_path.exists():
            return None
        try:
            raw = yaml.safe_load(self._cache_path.read_text())
            cache = UpdateCacheData.model_validate(raw)
            if time.time() - cache.timestamp > self._cache_interval:
                return None
            return cache.latest_version
        except (yaml.YAMLError, ValueError, TypeError):
            return None

    def _save_cache(self, latest_version: str) -> None:
        """Save version to cache file."""
        cache = UpdateCacheData(
            latest_version=latest_version,
            timestamp=time.time(),
        )
        self._cache_path.write_text(
            yaml.dump(cache.model_dump(), default_flow_style=False, sort_keys=False)
        )


def get_update_notice(current_version: str, cache_dir: Path) -> str | None:
    """Convenience function: check for updates and return formatted message or None.

    Constructs real dependencies internally. This is the function called from CLI wiring.
    """
    source = PyPIVersionSource()
    checker = UpdateChecker(source, current_version, cache_dir)
    result = checker.check()
    if result is not None:
        return result.message()
    return None

