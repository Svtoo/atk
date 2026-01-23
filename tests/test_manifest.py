"""Tests for manifest.yaml schema validation."""

import pytest

from atk.manifest import ConfigSection, ManifestSchema, PluginEntry


class TestPluginEntry:
    """Tests for plugin entry in manifest."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.valid_name = "OpenMemory"
        self.valid_directory = "openmemory"

    def test_plugin_entry_with_name_and_directory(self) -> None:
        """Verify plugin entry with both fields is valid."""
        # Given
        name = self.valid_name
        directory = self.valid_directory

        # When
        entry = PluginEntry(name=name, directory=directory)

        # Then
        assert entry.name == name
        assert entry.directory == directory

    def test_plugin_entry_name_is_required(self) -> None:
        """Verify that name field is required."""
        # Given
        directory = self.valid_directory

        # When/Then
        with pytest.raises(ValueError, match="name"):
            PluginEntry(directory=directory)  # type: ignore[call-arg]

    def test_plugin_entry_directory_is_required(self) -> None:
        """Verify that directory field is required."""
        # Given
        name = self.valid_name

        # When/Then
        with pytest.raises(ValueError, match="directory"):
            PluginEntry(name=name)  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "directory",
        [
            pytest.param("ab", id="minimum-2-chars"),
            pytest.param("openmemory", id="simple-name"),
            pytest.param("open-memory", id="with-hyphen"),
            pytest.param("plugin-v2", id="with-number-suffix"),
            pytest.param("my-cool-plugin", id="multiple-hyphens"),
            pytest.param("a1", id="letter-then-number"),
        ],
    )
    def test_directory_validation_valid_names(self, directory: str) -> None:
        """Verify valid directory names pass validation."""
        # Given
        name = "Test"

        # When
        entry = PluginEntry(name=name, directory=directory)

        # Then
        assert entry.directory == directory

    @pytest.mark.parametrize(
        "directory",
        [
            pytest.param("a", id="too-short"),
            pytest.param("A", id="uppercase-single"),
            pytest.param("OpenMemory", id="mixed-case"),
            pytest.param("open_memory", id="underscore-not-allowed"),
            pytest.param("1plugin", id="starts-with-number"),
            pytest.param("plugin-", id="ends-with-hyphen"),
            pytest.param("-plugin", id="starts-with-hyphen"),
            pytest.param("my--plugin", id="consecutive-hyphens"),
            pytest.param("open memory", id="contains-space"),
            pytest.param("open/memory", id="contains-slash"),
        ],
    )
    def test_directory_validation_invalid_names(self, directory: str) -> None:
        """Verify invalid directory names are rejected."""
        # Given
        name = "Test"

        # When/Then
        with pytest.raises(ValueError, match="directory"):
            PluginEntry(name=name, directory=directory)


class TestConfigSection:
    """Tests for manifest config section."""

    def test_config_defaults(self) -> None:
        """Verify config section has sensible defaults."""
        # Given/When
        config = ConfigSection()

        # Then - auto_commit defaults to True per spec
        assert config.auto_commit is True

    def test_config_auto_commit_can_be_disabled(self) -> None:
        """Verify auto_commit can be set to False."""
        # Given
        auto_commit = False

        # When
        config = ConfigSection(auto_commit=auto_commit)

        # Then
        assert config.auto_commit is False


class TestManifestSchema:
    """Tests for full manifest schema."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.schema_version = "2026-01-22"
        self.plugin_name = "OpenMemory"
        self.plugin_directory = "openmemory"

    def test_minimal_manifest(self) -> None:
        """Verify minimal manifest with only schema_version is valid."""
        # Given
        schema_version = self.schema_version

        # When
        manifest = ManifestSchema(schema_version=schema_version)

        # Then
        assert manifest.schema_version == schema_version
        # And - defaults
        assert manifest.config.auto_commit is True
        assert manifest.plugins == []

    def test_manifest_with_plugins(self) -> None:
        """Verify manifest with plugins list is valid."""
        # Given
        schema_version = self.schema_version
        plugin_name = self.plugin_name
        plugin_directory = self.plugin_directory
        plugins_data = [{"name": plugin_name, "directory": plugin_directory}]

        # When
        manifest = ManifestSchema(schema_version=schema_version, plugins=plugins_data)

        # Then
        assert len(manifest.plugins) == 1
        assert manifest.plugins[0].name == plugin_name
        assert manifest.plugins[0].directory == plugin_directory

    def test_manifest_with_config(self) -> None:
        """Verify manifest with config section is valid."""
        # Given
        schema_version = self.schema_version
        auto_commit = False
        config = ConfigSection(auto_commit=auto_commit)

        # When
        manifest = ManifestSchema(
            schema_version=schema_version,
            config=config,
        )

        # Then
        assert manifest.config.auto_commit == auto_commit

    def test_schema_version_is_required(self) -> None:
        """Verify schema_version is required."""
        # Given/When/Then
        with pytest.raises(ValueError, match="schema_version"):
            ManifestSchema()  # type: ignore[call-arg]

