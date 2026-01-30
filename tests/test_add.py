"""Tests for atk add command."""

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from atk.add import SourceType, add_plugin, detect_source_type, load_plugin_schema
from atk.cli import app
from atk.exit_codes import HOME_NOT_INITIALIZED, PLUGIN_INVALID, SUCCESS
from atk.init import init_atk_home
from atk.manifest_schema import ManifestSchema
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, EnvVarConfig, PluginSchema
from tests.conftest import write_plugin_yaml

runner = CliRunner()


def _noop_prompt(_text: str) -> str:
    """No-op prompt function for tests that don't care about env vars."""
    return ""


class TestDetectSourceType:
    """Tests for detect_source_type function."""

    def test_directory_with_plugin_yaml(self, tmp_path: Path) -> None:
        """Verify directory containing plugin.yaml is detected as directory source."""
        # Given
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        plugin_yaml = plugin_dir / "plugin.yaml"
        plugin_yaml.write_text("name: Test Plugin")

        # When
        result = detect_source_type(plugin_dir)

        # Then
        assert result == SourceType.DIRECTORY

    def test_single_yaml_file(self, tmp_path: Path) -> None:
        """Verify single .yaml file is detected as file source."""
        # Given
        plugin_yaml = tmp_path / "my-plugin.yaml"
        plugin_yaml.write_text("name: Test Plugin")

        # When
        result = detect_source_type(plugin_yaml)

        # Then
        assert result == SourceType.FILE

    def test_single_yml_file(self, tmp_path: Path) -> None:
        """Verify single .yml file is detected as file source."""
        # Given
        plugin_yml = tmp_path / "my-plugin.yml"
        plugin_yml.write_text("name: Test Plugin")

        # When
        result = detect_source_type(plugin_yml)

        # Then
        assert result == SourceType.FILE

    def test_directory_without_plugin_yaml_raises(self, tmp_path: Path) -> None:
        """Verify directory without plugin.yaml raises ValueError."""
        # Given
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()

        # When/Then
        with pytest.raises(ValueError, match="plugin.yaml"):
            detect_source_type(plugin_dir)

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        """Verify nonexistent path raises FileNotFoundError."""
        # Given
        nonexistent = tmp_path / "does-not-exist"

        # When/Then
        with pytest.raises(FileNotFoundError, match="does not exist"):
            detect_source_type(nonexistent)

    def test_non_yaml_file_raises(self, tmp_path: Path) -> None:
        """Verify non-yaml file raises ValueError."""
        # Given
        txt_file = tmp_path / "readme.txt"
        txt_file.write_text("Not a plugin")

        # When/Then
        with pytest.raises(ValueError, match="must be .yaml or .yml"):
            detect_source_type(txt_file)


class TestLoadPluginSchema:
    """Tests for load_plugin_schema function."""

    def test_load_valid_plugin_from_directory(self, tmp_path: Path) -> None:
        """Verify loading valid plugin.yaml from directory."""
        # Given
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        expected_plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="Test Plugin",
            description="A test plugin",
        )
        plugin_yaml = plugin_dir / "plugin.yaml"
        write_plugin_yaml(plugin_yaml, expected_plugin)

        # When
        actual = load_plugin_schema(plugin_dir)

        # Then
        assert actual.name == expected_plugin.name
        assert actual.description == expected_plugin.description
        assert actual.schema_version == expected_plugin.schema_version

    def test_load_valid_plugin_from_file(self, tmp_path: Path) -> None:
        """Verify loading valid plugin.yaml from single file."""
        # Given
        expected_plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="Single File Plugin",
            description="A single file plugin",
        )
        plugin_yaml = tmp_path / "my-plugin.yaml"
        write_plugin_yaml(plugin_yaml, expected_plugin)

        # When
        actual = load_plugin_schema(plugin_yaml)

        # Then
        assert actual.name == expected_plugin.name
        assert actual.description == expected_plugin.description
        assert actual.schema_version == expected_plugin.schema_version

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """Verify invalid YAML raises ValueError."""
        # Given
        plugin_yaml = tmp_path / "bad.yaml"
        plugin_yaml.write_text("not: valid: yaml: [")

        # When/Then
        with pytest.raises(ValueError, match="Invalid YAML"):
            load_plugin_schema(plugin_yaml)

    def test_load_missing_required_field_raises(self, tmp_path: Path) -> None:
        """Verify missing required field raises ValueError with clean message."""
        # Given
        plugin_yaml = tmp_path / "incomplete.yaml"
        plugin_yaml.write_text("""
schema_version: "2026-01-23"
name: "Missing Description"
""")

        # When/Then - error message should be clean (no Pydantic URL)
        with pytest.raises(ValueError, match="Invalid plugin.*description.*required"):
            load_plugin_schema(plugin_yaml)

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        """Verify nonexistent path raises FileNotFoundError."""
        # Given
        nonexistent = tmp_path / "does-not-exist"

        # When/Then
        with pytest.raises(FileNotFoundError):
            load_plugin_schema(nonexistent)


class TestAddPlugin:
    """Tests for add_plugin function."""

    def _create_plugin_source(self, tmp_path: Path, name: str) -> Path:
        """Helper to create a valid plugin source directory with plugin.yaml only."""
        plugin_dir = tmp_path / "source-plugin"
        plugin_dir.mkdir(exist_ok=True)
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name=name,
            description="A test plugin",
        )
        write_plugin_yaml(plugin_dir, plugin)
        return plugin_dir

    def test_add_plugin_from_directory(self, tmp_path: Path) -> None:
        """Verify adding plugin from directory copies all files and updates manifest."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # Create source directory with multiple files
        source_dir = tmp_path / "multi-file-plugin"
        source_dir.mkdir()
        plugin_name = "Test Plugin"
        expected_dir = "test-plugin"

        # Create plugin.yaml using model
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name=plugin_name,
            description="A test plugin with multiple files",
        )
        write_plugin_yaml(source_dir / "plugin.yaml", plugin)

        # Create additional files to verify they are copied
        readme_content = "# Test Plugin README"
        (source_dir / "README.md").write_text(readme_content)

        config_content = "key: value"
        (source_dir / "config.yaml").write_text(config_content)

        # Create a subdirectory with a file
        subdir = source_dir / "scripts"
        subdir.mkdir()
        script_content = "#!/bin/bash\necho hello"
        (subdir / "setup.sh").write_text(script_content)

        # When
        add_plugin(source_dir, atk_home, _noop_prompt)

        # Then - plugin directory exists with all files
        plugin_path = atk_home / "plugins" / expected_dir
        assert plugin_path.exists()
        assert (plugin_path / "plugin.yaml").exists()
        assert (plugin_path / "README.md").exists()
        assert (plugin_path / "README.md").read_text() == readme_content
        assert (plugin_path / "config.yaml").exists()
        assert (plugin_path / "config.yaml").read_text() == config_content
        assert (plugin_path / "scripts" / "setup.sh").exists()
        assert (plugin_path / "scripts" / "setup.sh").read_text() == script_content

        # Then - manifest updated
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 1
        assert manifest.plugins[0].name == plugin_name
        assert manifest.plugins[0].directory == expected_dir

    def test_add_plugin_from_single_file(self, tmp_path: Path) -> None:
        """Verify adding plugin from single file creates directory."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_name = "Single File Plugin"
        expected_dir = "single-file-plugin"
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name=plugin_name,
            description="A single file plugin",
        )
        plugin_yaml = tmp_path / "my-plugin.yaml"
        write_plugin_yaml(plugin_yaml, plugin)

        # When
        add_plugin(plugin_yaml, atk_home, _noop_prompt)

        # Then - plugin directory exists with only plugin.yaml
        plugin_path = atk_home / "plugins" / expected_dir
        assert plugin_path.exists()
        assert (plugin_path / "plugin.yaml").exists()

        # Then - manifest updated
        manifest_path = atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 1
        assert manifest.plugins[0].name == plugin_name

    def test_add_plugin_existing_raises(self, tmp_path: Path) -> None:
        """Verify adding plugin when directory already exists raises error."""
        # Given
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_name = "Existing Plugin"
        expected_dir = "existing-plugin"
        source = self._create_plugin_source(tmp_path, plugin_name)

        # Create existing plugin directory
        existing_dir = atk_home / "plugins" / expected_dir
        existing_dir.mkdir(parents=True)
        (existing_dir / "plugin.yaml").write_text("existing content")

        # When/Then
        with pytest.raises(ValueError, match="already exists"):
            add_plugin(source, atk_home, _noop_prompt)

    def test_add_plugin_to_uninitialized_home_raises(self, tmp_path: Path) -> None:
        """Verify adding to uninitialized ATK Home raises error."""
        # Given
        atk_home = tmp_path / "not-initialized"
        atk_home.mkdir()
        source = self._create_plugin_source(tmp_path, "Test")

        # When/Then
        with pytest.raises(ValueError, match="not initialized"):
            add_plugin(source, atk_home, _noop_prompt)


class TestAddCLI:
    """Tests for atk add CLI command."""

    @pytest.fixture(autouse=True)
    def setup_atk_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up ATK_HOME for each test."""
        self.atk_home = tmp_path / "atk-home"
        monkeypatch.setenv("ATK_HOME", str(self.atk_home))
        self.tmp_path = tmp_path

    def _create_plugin_source(self, name: str) -> Path:
        """Helper to create a valid plugin source directory."""
        plugin_dir = self.tmp_path / "source-plugin"
        plugin_dir.mkdir(exist_ok=True)
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name=name,
            description="A test plugin",
        )
        write_plugin_yaml(plugin_dir, plugin)
        return plugin_dir

    def test_add_success(self) -> None:
        """Verify successful add via CLI."""
        # Given
        init_atk_home(self.atk_home)
        plugin_name = "CLI Test Plugin"
        source = self._create_plugin_source(plugin_name)

        # When
        result = runner.invoke(app, ["add", str(source)])

        # Then
        assert result.exit_code == SUCCESS
        assert "Added plugin" in result.output

    def test_add_uninitialized_home(self) -> None:
        """Verify add fails when ATK Home not initialized."""
        # Given - ATK_HOME not initialized
        source = self._create_plugin_source("Test")

        # When
        result = runner.invoke(app, ["add", str(source)])

        # Then
        assert result.exit_code == HOME_NOT_INITIALIZED
        assert "not initialized" in result.output

    def test_add_nonexistent_source(self) -> None:
        """Verify add fails when source does not exist."""
        # Given
        init_atk_home(self.atk_home)
        nonexistent = self.tmp_path / "does-not-exist"

        # When
        result = runner.invoke(app, ["add", str(nonexistent)])

        # Then
        assert result.exit_code == PLUGIN_INVALID
        assert "does not exist" in result.output


class TestAddAutoCommit:
    """Tests for auto_commit behavior in add command."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up ATK_HOME for each test."""
        self.tmp_path = tmp_path
        self.atk_home = tmp_path / "atk-home"
        monkeypatch.setenv("ATK_HOME", str(self.atk_home))

    def test_add_creates_git_commit_when_auto_commit_true(self) -> None:
        """Verify add creates a git commit when auto_commit is enabled."""
        import subprocess

        # Given - initialized ATK home with auto_commit=true (default)
        init_atk_home(self.atk_home)
        source = Path("tests/fixtures/plugins/minimal-plugin")

        # When
        result = runner.invoke(app, ["add", str(source)])

        # Then - command succeeds
        assert result.exit_code == SUCCESS

        # And - git log shows a commit for adding the plugin
        git_result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=self.atk_home,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Add plugin" in git_result.stdout

    def test_add_skips_git_commit_when_auto_commit_false(self) -> None:
        """Verify add does NOT create a git commit when auto_commit is disabled."""
        import subprocess

        import yaml

        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - auto_commit is disabled in manifest
        manifest_path = self.atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest_data["config"]["auto_commit"] = False
        manifest_path.write_text(yaml.dump(manifest_data))

        # Get initial commit count
        initial_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=self.atk_home,
            capture_output=True,
            text=True,
            check=True,
        )
        initial_count = int(initial_result.stdout.strip())

        source = Path("tests/fixtures/plugins/minimal-plugin")

        # When
        result = runner.invoke(app, ["add", str(source)])

        # Then - command succeeds
        assert result.exit_code == SUCCESS

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


class TestAddInstallLifecycle:
    """Tests for install lifecycle integration in add command."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Set up ATK_HOME for each test."""
        self.tmp_path = tmp_path
        self.atk_home = tmp_path / "atk-home"
        monkeypatch.setenv("ATK_HOME", str(self.atk_home))

    def test_add_runs_install_lifecycle_when_defined(self) -> None:
        """Verify add runs install lifecycle command after copying files."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin with install lifecycle that creates a marker file
        plugin_dir = self.tmp_path / "marker-plugin"
        plugin_dir.mkdir()
        marker_file = self.tmp_path / "install-ran.marker"
        plugin_yaml = plugin_dir / "plugin.yaml"
        plugin_yaml.write_text(f"""
schema_version: "2026-01-23"
name: Marker Plugin
description: A plugin that creates a marker file on install
lifecycle:
  install: touch {marker_file}
""")

        # When
        result = runner.invoke(app, ["add", str(plugin_dir)])

        # Then - command succeeds
        assert result.exit_code == SUCCESS

        # And - install lifecycle was run (marker file exists)
        assert marker_file.exists(), "Install lifecycle should have created marker file"

    def test_add_skips_install_silently_when_not_defined(self) -> None:
        """Verify add skips install silently when plugin has no install command."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin without install lifecycle
        source = Path("tests/fixtures/plugins/minimal-plugin")

        # When
        result = runner.invoke(app, ["add", str(source)])

        # Then - command succeeds without warning about missing install
        assert result.exit_code == SUCCESS
        assert "Added plugin" in result.output
        # Should NOT warn about missing install (unlike standalone atk install)
        assert "not defined" not in result.output.lower()

    def test_add_fails_when_install_lifecycle_fails(self) -> None:
        """Verify add fails with exit code 6 when install lifecycle fails."""
        from atk.exit_codes import DOCKER_ERROR

        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin with failing install lifecycle
        plugin_dir = self.tmp_path / "failing-plugin"
        plugin_dir.mkdir()
        plugin_yaml = plugin_dir / "plugin.yaml"
        plugin_yaml.write_text("""
schema_version: "2026-01-23"
name: Failing Plugin
description: A plugin with failing install
lifecycle:
  install: exit 1
""")

        # When
        result = runner.invoke(app, ["add", str(plugin_dir)])

        # Then - command fails with DOCKER_ERROR (exit code 6)
        assert result.exit_code == DOCKER_ERROR
        assert "install" in result.output.lower() or "failed" in result.output.lower()

    def test_add_cleans_up_on_install_failure(self) -> None:
        """Verify add removes plugin directory if install fails."""
        # Given - initialized ATK home
        init_atk_home(self.atk_home)

        # And - a plugin with failing install lifecycle
        plugin_dir = self.tmp_path / "failing-plugin"
        plugin_dir.mkdir()
        plugin_yaml = plugin_dir / "plugin.yaml"
        plugin_yaml.write_text("""
schema_version: "2026-01-23"
name: Cleanup Test Plugin
description: A plugin with failing install
lifecycle:
  install: exit 1
""")

        # When
        runner.invoke(app, ["add", str(plugin_dir)])

        # Then - plugin directory should NOT exist (cleaned up)
        expected_dir = self.atk_home / "plugins" / "cleanup-test-plugin"
        assert not expected_dir.exists()

        # And - manifest should NOT contain the plugin
        manifest_path = self.atk_home / "manifest.yaml"
        manifest_data = yaml.safe_load(manifest_path.read_text())
        manifest = ManifestSchema.model_validate(manifest_data)
        assert len(manifest.plugins) == 0


class TestAddEnvVarSetup:
    """Tests for env var setup during add."""

    def test_add_runs_setup_when_plugin_has_env_vars(self, tmp_path: Path) -> None:
        """Verify add_plugin calls run_setup when plugin has env vars."""
        # Given - initialized ATK home
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # And - a source plugin with env vars
        source_dir = tmp_path / "env-plugin"
        source_dir.mkdir()
        api_key_value = "test-api-key-12345"
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="Env Plugin",
            description="A plugin with env vars",
            env_vars=[
                EnvVarConfig(
                    name="API_KEY",
                    required=True,
                    description="The API key",
                )
            ],
        )
        write_plugin_yaml(source_dir / "plugin.yaml", plugin)

        # And - a prompt function that returns a known value
        def prompt_func(_text: str) -> str:
            return api_key_value

        # When
        add_plugin(source_dir, atk_home, prompt_func)

        # Then - .env file should exist with the prompted value
        env_file = atk_home / "plugins" / "env-plugin" / ".env"
        assert env_file.exists()
        content = env_file.read_text()
        assert content == f"# The API key\nAPI_KEY={api_key_value}\n"

    def test_add_skips_setup_when_no_env_vars(self, tmp_path: Path) -> None:
        """Verify add_plugin skips setup when plugin has no env vars."""
        # Given - initialized ATK home
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # And - a source plugin without env vars
        source_dir = tmp_path / "simple-plugin"
        source_dir.mkdir()
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="Simple Plugin",
            description="A plugin without env vars",
        )
        write_plugin_yaml(source_dir / "plugin.yaml", plugin)

        # And - a prompt function that should NOT be called
        prompt_called = False

        def prompt_func(_text: str) -> str:
            nonlocal prompt_called
            prompt_called = True
            return "should-not-be-called"

        # When
        add_plugin(source_dir, atk_home, prompt_func)

        # Then - prompt should not have been called
        assert not prompt_called

        # And - .env file should NOT exist
        env_file = atk_home / "plugins" / "simple-plugin" / ".env"
        assert not env_file.exists()
