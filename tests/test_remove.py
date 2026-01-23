"""Tests for atk remove command."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.init import init_atk_home
from atk.manifest_schema import ManifestSchema
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, PluginSchema
from atk.remove import remove_plugin

runner = CliRunner()


def _serialize_plugin(plugin: PluginSchema) -> str:
    """Serialize a PluginSchema to YAML string."""
    return yaml.dump(plugin.model_dump(exclude_none=True), default_flow_style=False)


def _add_plugin_to_home(atk_home: Path, name: str, directory: str) -> Path:
    """Helper to manually add a plugin to ATK Home for testing."""
    # Create plugin directory
    plugin_dir = atk_home / "plugins" / directory
    plugin_dir.mkdir(parents=True)

    # Create plugin.yaml
    plugin = PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description=f"Test plugin: {name}",
    )
    (plugin_dir / "plugin.yaml").write_text(_serialize_plugin(plugin))

    # Update manifest
    manifest_path = atk_home / "manifest.yaml"
    manifest_data = yaml.safe_load(manifest_path.read_text())
    manifest = ManifestSchema.model_validate(manifest_data)
    manifest.plugins.append(
        ManifestSchema.model_fields["plugins"].annotation.__args__[0](
            name=name, directory=directory
        )
    )
    manifest_path.write_text(
        yaml.dump(manifest.model_dump(), default_flow_style=False, sort_keys=False)
    )

    return plugin_dir


class TestRemovePlugin:
    """Tests for remove_plugin function."""

    def test_remove_existing_plugin(self, tmp_path: Path) -> None:
        """Verify removing an existing plugin deletes directory and updates manifest."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_name = "Test Plugin"
        directory = "test-plugin"
        plugin_dir = _add_plugin_to_home(atk_home, plugin_name, directory)

        # When
        remove_plugin(directory, atk_home)

        # Then - plugin directory is gone
        assert not plugin_dir.exists()

        # Then - manifest no longer contains plugin
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 0

    def test_remove_nonexistent_plugin_is_noop(self, tmp_path: Path) -> None:
        """Verify removing nonexistent plugin is a no-op (idempotent)."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # When - remove plugin that doesn't exist
        remove_plugin("does-not-exist", atk_home)

        # Then - no error, manifest unchanged
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 0

    def test_remove_plugin_uninitialized_home_raises(self, tmp_path: Path) -> None:
        """Verify removing from uninitialized ATK Home raises error."""
        # Given
        atk_home = tmp_path / "not-initialized"
        atk_home.mkdir()

        # When/Then
        with pytest.raises(ValueError, match="not initialized"):
            remove_plugin("some-plugin", atk_home)

    def test_remove_one_of_multiple_plugins(self, tmp_path: Path) -> None:
        """Verify removing one plugin leaves others intact."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # Add two plugins
        plugin1_dir = _add_plugin_to_home(atk_home, "Plugin One", "plugin-one")
        plugin2_dir = _add_plugin_to_home(atk_home, "Plugin Two", "plugin-two")

        # When - remove first plugin
        remove_plugin("plugin-one", atk_home)

        # Then - first plugin gone, second remains
        assert not plugin1_dir.exists()
        assert plugin2_dir.exists()

        # Then - manifest only has second plugin
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 1
        assert manifest.plugins[0].directory == "plugin-two"

    def test_remove_plugin_by_name(self, tmp_path: Path) -> None:
        """Verify removing by plugin name works (not just directory)."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_name = "My Plugin"
        directory = "my-plugin"
        plugin_dir = _add_plugin_to_home(atk_home, plugin_name, directory)

        # When - remove by name instead of directory
        result = remove_plugin(plugin_name, atk_home)

        # Then - plugin is removed
        assert result is True
        assert not plugin_dir.exists()

        # Then - manifest no longer contains plugin
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 0


class TestRemoveCLI:
    """Tests for atk remove CLI command."""

    def test_cli_remove_existing_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI removes plugin and exits with success."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        directory = "test-plugin"
        _add_plugin_to_home(atk_home, "Test Plugin", directory)

        # When
        result = runner.invoke(app, ["remove", directory])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "Removed plugin" in result.stdout
        assert not (atk_home / "plugins" / directory).exists()

    def test_cli_remove_nonexistent_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI handles nonexistent plugin gracefully."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["remove", "does-not-exist"])

        # Then
        assert result.exit_code == exit_codes.SUCCESS
        assert "not found" in result.stdout

    def test_cli_remove_uninitialized_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI errors when ATK Home not initialized."""
        # Given
        atk_home = tmp_path / "not-initialized"
        monkeypatch.setenv("ATK_HOME", str(atk_home))

        # When
        result = runner.invoke(app, ["remove", "some-plugin"])

        # Then
        assert result.exit_code == exit_codes.HOME_NOT_INITIALIZED
        assert "not initialized" in result.stdout

    def test_cli_add_two_remove_one_leaves_other(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify removing one plugin via CLI leaves other plugins intact.

        Regression test: Bug where removing one plugin deleted all plugins.
        Uses actual CLI add/remove flow, not test helpers.
        """
        # Given - initialize ATK Home
        atk_home = tmp_path / "atk-home"
        monkeypatch.setenv("ATK_HOME", str(atk_home))
        runner.invoke(app, ["init"])

        # Given - add two plugins via CLI using fixtures
        fixtures_dir = Path(__file__).parent / "fixtures" / "plugins"
        full_plugin_path = fixtures_dir / "full-plugin"
        minimal_plugin_path = fixtures_dir / "minimal-plugin"

        result1 = runner.invoke(app, ["add", str(full_plugin_path)])
        assert result1.exit_code == exit_codes.SUCCESS, f"Failed to add full-plugin: {result1.stdout}"

        result2 = runner.invoke(app, ["add", str(minimal_plugin_path)])
        assert result2.exit_code == exit_codes.SUCCESS, f"Failed to add minimal-plugin: {result2.stdout}"

        # Verify both plugins exist
        assert (atk_home / "plugins" / "full-plugin").exists()
        assert (atk_home / "plugins" / "minimal-plugin").exists()

        # When - remove one plugin by name
        result = runner.invoke(app, ["remove", "Full Plugin"])

        # Then - removal succeeded
        assert result.exit_code == exit_codes.SUCCESS
        assert "Removed plugin" in result.stdout

        # Then - removed plugin is gone
        assert not (atk_home / "plugins" / "full-plugin").exists()

        # Then - other plugin still exists
        assert (atk_home / "plugins" / "minimal-plugin").exists()

        # Then - manifest only has remaining plugin
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 1
        remaining_plugin = manifest.plugins[0]
        assert remaining_plugin.directory == "minimal-plugin"
        assert remaining_plugin.name == "Minimal Plugin"
