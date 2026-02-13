"""Tests for atk.update_check module."""

import time
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from atk.update_check import (
    CACHE_FILENAME,
    UpdateCacheData,
    UpdateChecker,
    UpdateInfo,
    VersionSource,
    get_update_notice,
)


def _write_cache(cache_dir: Path, latest_version: str, timestamp: float) -> None:
    """Write a cache file using the same format as production code."""
    cache = UpdateCacheData(latest_version=latest_version, timestamp=timestamp)
    (cache_dir / CACHE_FILENAME).write_text(
        yaml.dump(cache.model_dump(), default_flow_style=False, sort_keys=False)
    )


class TestUpdateInfo:
    """Tests for UpdateInfo dataclass."""

    def test_message_format_is_exact(self) -> None:
        """Spec #10: Message format is exact."""
        # Given
        current = "0.0.1"
        latest = "0.0.2"
        info = UpdateInfo(current=current, latest=latest)

        # When
        actual = info.message()

        # Then
        expected = f"Update available: {current} → {latest}\nRun: uv tool upgrade atk-cli"
        assert actual == expected


class TestUpdateChecker:
    """Tests for UpdateChecker service."""

    def test_shows_update_when_newer_version_exists(self, tmp_path: Path) -> None:
        """Spec #1: Shows update when newer version exists."""
        # Given
        current = "0.0.1"
        latest = "0.0.2"
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path)

        # When
        result = checker.check()

        # Then
        assert result is not None
        assert result.current == current
        assert result.latest == latest

    def test_no_update_when_up_to_date(self, tmp_path: Path) -> None:
        """Spec #2: No update when up to date."""
        # Given
        current = "0.0.2"
        latest = "0.0.2"
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path)

        # When
        result = checker.check()

        # Then
        assert result is None

    def test_no_update_when_ahead(self, tmp_path: Path) -> None:
        """Spec #3: No update when ahead (dev build)."""
        # Given
        current = "0.0.3"
        latest = "0.0.2"
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path)

        # When
        result = checker.check()

        # Then
        assert result is None

    @pytest.mark.parametrize(
        ("current", "latest", "expect_update"),
        [
            # Standard semver bumps
            pytest.param("0.0.1", "0.0.2", True, id="patch-bump"),
            pytest.param("0.0.1", "0.1.0", True, id="minor-bump"),
            pytest.param("0.0.1", "1.0.0", True, id="major-bump"),
            pytest.param("1.0.0", "1.0.1", True, id="standard-semver-patch"),
            pytest.param("1.2.3", "1.2.4", True, id="mid-range-patch"),
            pytest.param("1.2.3", "1.3.0", True, id="mid-range-minor"),
            pytest.param("1.2.3", "2.0.0", True, id="mid-range-major"),
            # Equal versions — no update
            pytest.param("1.0.0", "1.0.0", False, id="equal"),
            pytest.param("0.0.1", "0.0.1", False, id="equal-low"),
            # Current ahead — no update
            pytest.param("0.0.3", "0.0.2", False, id="ahead-patch"),
            pytest.param("0.1.0", "0.0.9", False, id="ahead-minor"),
            pytest.param("2.0.0", "1.9.9", False, id="ahead-major"),
            # Different segment counts
            pytest.param("1.0", "1.0.1", True, id="two-seg-current-three-seg-latest"),
            pytest.param("1.0.1", "1.0", False, id="three-seg-current-two-seg-latest"),
            pytest.param("1.0.0", "1.0.0.0", True, id="extra-trailing-zero-on-latest"),
            pytest.param("1.0.0.0", "1.0.0", False, id="extra-trailing-zero-on-current"),
            # Single segment
            pytest.param("1", "2", True, id="single-segment-bump"),
            pytest.param("2", "2", False, id="single-segment-equal"),
            pytest.param("3", "2", False, id="single-segment-ahead"),
            # Edge cases
            pytest.param("0.0.0", "0.0.1", True, id="zero-to-first"),
            pytest.param("99.99.99", "100.0.0", True, id="large-version-numbers"),
            pytest.param("0.9.9", "0.10.0", True, id="numeric-not-lexicographic"),
        ],
    )
    def test_version_comparison(
        self, tmp_path: Path, current: str, latest: str, expect_update: bool
    ) -> None:
        """Verify version comparison across various version formats and edge cases."""
        # Given
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path)

        # When
        result = checker.check()

        # Then
        if expect_update:
            assert result is not None, f"Expected update from {current} → {latest}"
            assert result.current == current
            assert result.latest == latest
        else:
            assert result is None, f"Expected no update from {current} → {latest}"

    def test_no_update_when_source_fails(self, tmp_path: Path) -> None:
        """Spec #4: No update when source fails."""
        # Given
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = None
        checker = UpdateChecker(source, "0.0.1", tmp_path)

        # When
        result = checker.check()

        # Then
        assert result is None

    def test_caches_result_after_first_fetch(self, tmp_path: Path) -> None:
        """Spec #5: Caches result after first fetch."""
        # Given
        current = "0.0.1"
        latest = "0.0.2"
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path)

        # When
        checker.check()
        checker.check()

        # Then — source called only once
        source.fetch_latest.assert_called_once()

    def test_refetches_after_cache_expires(self, tmp_path: Path) -> None:
        """Spec #6: Re-fetches after cache expires."""
        # Given — cache with expired timestamp
        current = "0.0.1"
        latest = "0.0.2"
        cache_interval = 100
        expired_timestamp = time.time() - cache_interval - 1
        _write_cache(tmp_path, latest, expired_timestamp)

        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path, cache_interval=cache_interval)

        # When
        checker.check()

        # Then — source was called because cache expired
        source.fetch_latest.assert_called_once()

    def test_uses_cached_version_for_comparison(self, tmp_path: Path) -> None:
        """Spec #7: Uses cached version for comparison."""
        # Given — valid cache with a newer version
        current = "0.0.1"
        cached_latest = "0.0.2"
        _write_cache(tmp_path, cached_latest, time.time())

        source = Mock(spec=VersionSource)
        checker = UpdateChecker(source, current, tmp_path)

        # When
        result = checker.check()

        # Then — used cache, did not call source
        source.fetch_latest.assert_not_called()
        assert result is not None
        assert result.latest == cached_latest

    def test_handles_corrupt_cache_file(self, tmp_path: Path) -> None:
        """Spec #8: Handles corrupt cache file."""
        # Given — cache file with invalid YAML
        (tmp_path / CACHE_FILENAME).write_text(": [invalid yaml{{{")
        current = "0.0.1"
        latest = "0.0.2"
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = latest
        checker = UpdateChecker(source, current, tmp_path)

        # When
        result = checker.check()

        # Then — fetched fresh, did not crash
        source.fetch_latest.assert_called_once()
        assert result is not None
        assert result.latest == latest

    def test_does_not_cache_when_source_fails(self, tmp_path: Path) -> None:
        """Spec #9: Does not cache when source fails."""
        # Given
        source = Mock(spec=VersionSource)
        source.fetch_latest.return_value = None
        cache_path = tmp_path / CACHE_FILENAME
        checker = UpdateChecker(source, "0.0.1", tmp_path)

        # When
        checker.check()

        # Then — no cache file written
        assert not cache_path.exists()


class TestGetUpdateNotice:
    """Tests for get_update_notice convenience function."""

    def test_returns_formatted_string_when_update_available(self, tmp_path: Path) -> None:
        """Spec #11: get_update_notice returns formatted string."""
        # Given — a checker that will find an update
        current = "0.0.1"
        latest = "0.0.2"
        # Pre-populate cache so we don't hit real PyPI
        _write_cache(tmp_path, latest, time.time())

        # When
        result = get_update_notice(current, tmp_path)

        # Then
        expected = f"Update available: {current} → {latest}\nRun: uv tool upgrade atk-cli"
        assert result == expected

    def test_returns_none_when_up_to_date(self, tmp_path: Path) -> None:
        """Spec #12: get_update_notice returns None."""
        # Given — cache says same version
        current = "0.0.2"
        latest = "0.0.2"
        _write_cache(tmp_path, latest, time.time())

        # When
        result = get_update_notice(current, tmp_path)

        # Then
        assert result is None

