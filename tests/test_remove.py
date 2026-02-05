"""Tests for atk remove command."""

import subprocess
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk import exit_codes
from atk.cli import app
from atk.git import add_gitignore_exemption
from atk.init import GITIGNORE_CONTENT, init_atk_home
from atk.manifest_schema import ManifestSchema, PluginEntry, load_manifest, save_manifest
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, PluginSchema
from atk.remove import remove_plugin
from tests.conftest import write_plugin_yaml

runner = CliRunner()


def _add_plugin_to_home(atk_home: Path, name: str, directory: str, source: str = "local") -> Path:
    """Helper to manually add a plugin to ATK Home for testing.

    Creates a plugin directory with plugin.yaml and updates the manifest.
    Does NOT add gitignore exemptions - that's business logic for add_plugin.

    Args:
        atk_home: Path to ATK Home directory.
        name: Plugin name.
        directory: Plugin directory name.
        source: Source type ('local', 'registry', 'git'). Defaults to 'local'.
    """
    # Create plugin directory
    plugin_dir = atk_home / "plugins" / directory
    plugin_dir.mkdir(parents=True)

    # Create plugin.yaml
    plugin = PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description=f"Test plugin: {name}",
    )
    write_plugin_yaml(plugin_dir, plugin)

    # Update manifest
    manifest = load_manifest(atk_home)
    manifest.plugins.append(PluginEntry(name=name, directory=directory, source=source))
    save_manifest(manifest, atk_home)

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
        assert result.removed is True
        assert not plugin_dir.exists()

        # Then - manifest no longer contains plugin
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 0

    def test_remove_local_plugin_removes_gitignore_exemption(self, tmp_path: Path) -> None:
        """Verify removing a local plugin removes its gitignore exemption."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_name = "Local Plugin"
        directory = "local-plugin"
        exemption_dir = f"!plugins/{directory}/"
        exemption_glob = f"!plugins/{directory}/**"

        # Add plugin with source='local' and manually add gitignore exemption
        plugin_dir = _add_plugin_to_home(atk_home, plugin_name, directory, source="local")
        add_gitignore_exemption(atk_home, directory)

        # Verify gitignore exemption exists
        gitignore_path = atk_home / ".gitignore"
        expected_before = f"{GITIGNORE_CONTENT}{exemption_dir}\n{exemption_glob}\n"
        actual_before = gitignore_path.read_text()
        assert actual_before == expected_before

        # When
        remove_plugin(directory, atk_home)

        # Then - gitignore exemption is removed, only original content remains
        actual_after = gitignore_path.read_text()
        assert actual_after == GITIGNORE_CONTENT

        # Then - plugin directory is gone
        assert not plugin_dir.exists()

    def test_remove_non_local_plugin_does_not_touch_gitignore(self, tmp_path: Path) -> None:
        """Verify removing a non-local plugin doesn't modify gitignore."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_name = "Non-Local Plugin"
        directory = "non-local-plugin"

        # Add plugin with source='registry' (non-local)
        plugin_dir = _add_plugin_to_home(atk_home, plugin_name, directory, source="registry")

        # Get initial gitignore content
        gitignore_path = atk_home / ".gitignore"
        initial_gitignore = gitignore_path.read_text()

        # When
        remove_plugin(directory, atk_home)

        # Then - gitignore unchanged
        final_gitignore = gitignore_path.read_text()
        assert final_gitignore == initial_gitignore

        # Then - plugin directory is gone
        assert not plugin_dir.exists()


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

        # full-plugin has 2 env vars (FULL_PLUGIN_API_KEY required, FULL_PLUGIN_DEBUG optional)
        # Provide input for both prompts
        result1 = runner.invoke(
            app, ["add", str(full_plugin_path)], input="test-api-key\nfalse\n"
        )
        assert result1.exit_code == exit_codes.SUCCESS, f"Failed to add full-plugin: {result1.stdout}"

        # minimal-plugin has no env vars
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


class TestRemoveAutoCommit:
    """Tests for auto_commit behavior in remove command."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up ATK_HOME for each test."""
        self.tmp_path = tmp_path
        self.atk_home = tmp_path / "atk-home"
        monkeypatch.setenv("ATK_HOME", str(self.atk_home))

    def test_remove_creates_git_commit_when_auto_commit_true(self) -> None:
        """Verify remove creates a git commit when auto_commit is enabled."""
        # Given - initialized ATK home with a plugin added via atk add (creates commit)
        init_atk_home(self.atk_home)
        source = Path("tests/fixtures/plugins/minimal-plugin")
        add_result = runner.invoke(app, ["add", str(source)])
        assert add_result.exit_code == exit_codes.SUCCESS

        # When
        result = runner.invoke(app, ["remove", "minimal-plugin"])

        # Then - command succeeds
        assert result.exit_code == exit_codes.SUCCESS

        # And - git log shows a commit for removing the plugin
        git_result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=self.atk_home,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Remove plugin" in git_result.stdout

    def test_remove_skips_git_commit_when_auto_commit_false(self) -> None:
        """Verify remove does NOT create a git commit when auto_commit is disabled."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - auto_commit is disabled in manifest
        manifest_path = self.atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest_data["config"]["auto_commit"] = False
        manifest_path.write_text(yaml.dump(manifest_data))

        # And - add a plugin manually
        _add_plugin_to_home(self.atk_home, "Test Plugin", "test-plugin")

        # Get initial commit count
        initial_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.atk_home,
            capture_output=True,
            text=True,
            check=True,
        )
        initial_count = int(initial_result.stdout.strip())

        # When
        result = runner.invoke(app, ["remove", "test-plugin"])

        # Then - command succeeds
        assert result.exit_code == exit_codes.SUCCESS

        # And - no new commit was created
        final_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.atk_home,
            capture_output=True,
            text=True,
            check=True,
        )
        final_count = int(final_result.stdout.strip())
        assert final_count == initial_count


class TestRemoveStopLifecycle:
    """Tests for stop lifecycle integration in remove command."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up ATK_HOME for each test."""
        self.tmp_path = tmp_path
        self.atk_home = tmp_path / "atk-home"
        monkeypatch.setenv("ATK_HOME", str(self.atk_home))

    def test_remove_runs_stop_lifecycle_when_defined(self) -> None:
        """Verify remove runs stop lifecycle command before removing files."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin with stop lifecycle that creates a marker file
        marker_file = self.tmp_path / "stop-ran.marker"
        plugin_dir = self.atk_home / "plugins" / "marker-plugin"
        plugin_dir.mkdir(parents=True)
        plugin_yaml = plugin_dir / "plugin.yaml"
        plugin_yaml.write_text(f"""
schema_version: "2026-01-23"
name: Marker Plugin
description: A plugin that creates a marker file on stop
lifecycle:
  stop: touch {marker_file}
""")

        # And - plugin is in manifest
        manifest = load_manifest(self.atk_home)
        manifest.plugins.append(
            PluginEntry(name="Marker Plugin", directory="marker-plugin", source="local")
        )
        save_manifest(manifest, self.atk_home)

        # When
        result = runner.invoke(app, ["remove", "marker-plugin"])

        # Then - command succeeds
        assert result.exit_code == exit_codes.SUCCESS

        # And - stop lifecycle was run (marker file exists)
        assert marker_file.exists(), "Stop lifecycle should have created marker file"

        # And - plugin was removed
        assert not plugin_dir.exists()

    def test_remove_skips_stop_silently_when_not_defined(self) -> None:
        """Verify remove skips stop silently when plugin has no stop command."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin without stop lifecycle
        _add_plugin_to_home(self.atk_home, "No Stop Plugin", "no-stop-plugin")

        # When
        result = runner.invoke(app, ["remove", "no-stop-plugin"])

        # Then - command succeeds without warning about missing stop
        assert result.exit_code == exit_codes.SUCCESS
        assert "Removed plugin" in result.stdout
        # Should NOT warn about missing stop
        assert "not defined" not in result.stdout.lower()

    def test_remove_continues_when_stop_lifecycle_fails(self) -> None:
        """Verify remove continues with removal even if stop lifecycle fails."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin with failing stop lifecycle
        plugin_dir = self.atk_home / "plugins" / "failing-stop-plugin"
        plugin_dir.mkdir(parents=True)
        plugin_yaml = plugin_dir / "plugin.yaml"
        plugin_yaml.write_text("""
schema_version: "2026-01-23"
name: Failing Stop Plugin
description: A plugin with failing stop
lifecycle:
  stop: exit 1
""")

        # And - plugin is in manifest
        manifest = load_manifest(self.atk_home)
        manifest.plugins.append(
            PluginEntry(name="Failing Stop Plugin", directory="failing-stop-plugin", source="local")
        )
        save_manifest(manifest, self.atk_home)

        # When
        result = runner.invoke(app, ["remove", "failing-stop-plugin"])

        # Then - command still succeeds (removal continues despite stop failure)
        assert result.exit_code == exit_codes.SUCCESS

        # And - plugin was still removed
        assert not plugin_dir.exists()

        # And - user was warned about stop failure
        assert "warning" in result.stdout.lower() or "failed" in result.stdout.lower()
