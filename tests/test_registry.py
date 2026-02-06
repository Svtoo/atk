"""Tests for registry fetch.

Tests fetching plugin files from the registry git repo.
"""

from pathlib import Path

import pytest

from atk.registry import (
    PluginNotFoundError,
    RegistryFetchError,
    fetch_registry_plugin,
)
from tests.conftest import create_fake_registry


class TestFetchRegistryPlugin:
    """Tests for fetching a plugin from the registry by name.

    These tests create a local git repo that mimics the registry structure,
    then fetch from it — no network required.
    """

    def test_fetches_plugin_by_name(self, tmp_path: Path) -> None:
        """Fetch copies the plugin directory to the target location."""
        registry = create_fake_registry(tmp_path)
        plugin_name = "test-plugin"
        target_dir = tmp_path / "target"

        result = fetch_registry_plugin(
            name=plugin_name,
            target_dir=target_dir,
            registry_url=registry.url,
        )

        assert target_dir.exists()
        assert (target_dir / "plugin.yaml").exists()
        assert (target_dir / "docker-compose.yml").exists()
        assert result.commit_hash == registry.commit_hash

    def test_returns_full_commit_hash(self, tmp_path: Path) -> None:
        """Fetch returns the full 40-char commit hash for version pinning."""
        registry = create_fake_registry(tmp_path)
        target_dir = tmp_path / "target"

        result = fetch_registry_plugin(
            name="test-plugin",
            target_dir=target_dir,
            registry_url=registry.url,
        )

        assert result.commit_hash == registry.commit_hash

    def test_plugin_not_found_raises(self, tmp_path: Path) -> None:
        """Fetch raises PluginNotFoundError when plugin name is not in the index."""
        registry = create_fake_registry(tmp_path)
        nonexistent_name = "nonexistent"
        target_dir = tmp_path / "target"

        with pytest.raises(PluginNotFoundError, match=nonexistent_name):
            fetch_registry_plugin(
                name=nonexistent_name,
                target_dir=target_dir,
                registry_url=registry.url,
            )

    def test_invalid_registry_url_raises(self, tmp_path: Path) -> None:
        """Fetch raises RegistryFetchError when registry URL is unreachable."""
        target_dir = tmp_path / "target"

        with pytest.raises(RegistryFetchError):
            fetch_registry_plugin(
                name="test-plugin",
                target_dir=target_dir,
                registry_url="https://nonexistent.invalid/repo",
            )

