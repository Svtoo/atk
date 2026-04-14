"""Tests for registry fetch.

Tests fetching plugin files from the registry git repo.
"""

import subprocess
from pathlib import Path

import pytest
import yaml

from atk.registry import (
    PluginNotFoundError,
    RegistryFetchError,
    fetch_registry_index,
    fetch_registry_plugin,
)
from tests.conftest import create_fake_registry, git_commit_all


class TestFetchRegistryIndex:
    """Tests for fetching the registry index.

    Uses a local git repo so no network access is required.
    """

    def test_returns_index_with_all_plugins(self, tmp_path: Path) -> None:
        """Returns a parsed index containing the plugins present in the registry."""
        registry = create_fake_registry(tmp_path)
        plugin_name = "test-plugin"
        plugin_description = "A test plugin"

        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        index = fetch_registry_index(atk_home=atk_home, registry_url=registry.url)

        assert len(index.plugins) == 1
        assert index.plugins[0].name == plugin_name
        assert index.plugins[0].description == plugin_description

    def test_unreachable_url_raises_registry_fetch_error(self, tmp_path: Path) -> None:
        """Raises RegistryFetchError when the registry URL is not reachable."""
        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        with pytest.raises(RegistryFetchError):
            fetch_registry_index(atk_home=atk_home, registry_url="https://nonexistent.invalid/repo")


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

        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        result = fetch_registry_plugin(
            name=plugin_name,
            target_dir=target_dir,
            ref=registry.commit_hash,
            atk_home=atk_home,
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

        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        result = fetch_registry_plugin(
            name="test-plugin",
            target_dir=target_dir,
            ref=registry.commit_hash,
            atk_home=atk_home,
            registry_url=registry.url,
        )

        assert result.commit_hash == registry.commit_hash

    def test_plugin_not_found_raises(self, tmp_path: Path) -> None:
        """Fetch raises PluginNotFoundError when plugin name is not in the index."""
        registry = create_fake_registry(tmp_path)
        nonexistent_name = "nonexistent"
        target_dir = tmp_path / "target"

        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        with pytest.raises(PluginNotFoundError, match=nonexistent_name):
            fetch_registry_plugin(
                name=nonexistent_name,
                target_dir=target_dir,
                ref=registry.commit_hash,
                atk_home=atk_home,
                registry_url=registry.url,
            )

    def test_invalid_registry_url_raises(self, tmp_path: Path) -> None:
        """Fetch raises RegistryFetchError when registry URL is unreachable."""
        target_dir = tmp_path / "target"

        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        with pytest.raises(RegistryFetchError):
            fetch_registry_plugin(
                name="test-plugin",
                target_dir=target_dir,
                ref="deadbeef" * 5,
                atk_home=atk_home,
                registry_url="https://nonexistent.invalid/repo",
            )

    def test_invalid_index_schema_raises_registry_fetch_error(self, tmp_path: Path) -> None:
        """Fetch raises RegistryFetchError when index.yaml has invalid schema."""
        # Given - registry with invalid index (plugin entry missing required fields)
        work_dir = tmp_path / "registry-work"
        work_dir.mkdir()
        invalid_plugin_entry = {"name": "test-plugin"}  # missing path and description
        (work_dir / "index.yaml").write_text(
            yaml.dump({"plugins": [invalid_plugin_entry]})
        )
        subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)
        commit_hash = git_commit_all(work_dir, "Initial")
        registry_url = f"file://{work_dir}"
        target_dir = tmp_path / "target"

        # Create a mock ATK home for the test
        atk_home = tmp_path / "atk-home"
        atk_home.mkdir()

        # When/Then
        expected_match = "Invalid registry index"
        with pytest.raises(RegistryFetchError, match=expected_match):
            fetch_registry_plugin(
                name="test-plugin",
                target_dir=target_dir,
                ref=commit_hash,
                atk_home=atk_home,
                registry_url=registry_url,
            )
