"""Tests for MCP configuration generation."""

from pathlib import Path

import pytest

from atk.mcp import generate_mcp_config, substitute_plugin_dir
from atk.plugin_schema import McpConfig, PluginSchema


class TestSubstitutePluginDir:
    """Tests for ATK_PLUGIN_DIR substitution."""

    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path) -> None:
        """Set up plugin directory for each test."""
        self.plugin_dir = tmp_path / "plugins" / "test-plugin"

    def test_substitute_dollar_syntax(self) -> None:
        """Verify $ATK_PLUGIN_DIR is substituted with absolute path."""
        # Given
        command = "$ATK_PLUGIN_DIR/mcp-server.sh"

        # When
        result = substitute_plugin_dir(command, self.plugin_dir)

        # Then
        expected = f"{self.plugin_dir.resolve()}/mcp-server.sh"
        assert result == expected

    def test_substitute_braces_syntax(self) -> None:
        """Verify ${ATK_PLUGIN_DIR} is substituted with absolute path."""
        # Given
        command = "${ATK_PLUGIN_DIR}/mcp-server.sh"

        # When
        result = substitute_plugin_dir(command, self.plugin_dir)

        # Then
        expected = f"{self.plugin_dir.resolve()}/mcp-server.sh"
        assert result == expected

    def test_substitute_multiple_occurrences(self) -> None:
        """Verify multiple occurrences of $ATK_PLUGIN_DIR are all substituted."""
        # Given
        value = "$ATK_PLUGIN_DIR/bin:$ATK_PLUGIN_DIR/lib"

        # When
        result = substitute_plugin_dir(value, self.plugin_dir)

        # Then
        plugin_dir_str = str(self.plugin_dir.resolve())
        expected = f"{plugin_dir_str}/bin:{plugin_dir_str}/lib"
        assert result == expected

    def test_substitute_mixed_syntax(self) -> None:
        """Verify both $VAR and ${VAR} syntax work in same string."""
        # Given
        value = "$ATK_PLUGIN_DIR/bin:${ATK_PLUGIN_DIR}/lib"

        # When
        result = substitute_plugin_dir(value, self.plugin_dir)

        # Then
        plugin_dir_str = str(self.plugin_dir.resolve())
        expected = f"{plugin_dir_str}/bin:{plugin_dir_str}/lib"
        assert result == expected

    def test_no_substitution_when_variable_not_present(self) -> None:
        """Verify strings without $ATK_PLUGIN_DIR are unchanged."""
        # Given
        command = "/usr/bin/python"

        # When
        result = substitute_plugin_dir(command, self.plugin_dir)

        # Then
        assert result == command

    def test_substitute_in_arg_with_path(self) -> None:
        """Verify substitution works in arguments like --config=$ATK_PLUGIN_DIR/config.json."""
        # Given
        arg = "--config=$ATK_PLUGIN_DIR/config.json"

        # When
        result = substitute_plugin_dir(arg, self.plugin_dir)

        # Then
        expected = f"--config={self.plugin_dir.resolve()}/config.json"
        assert result == expected


class TestGenerateMcpConfigWithSubstitution:
    """Tests for generate_mcp_config with ATK_PLUGIN_DIR substitution."""
    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path: Path) -> None:
        """Set up plugin directory for each test."""
        self.plugin_dir = tmp_path / "plugins" / "test-plugin"

    def test_substitutes_command(self) -> None:
        """Verify command field is substituted."""
        # Given
        command = "$ATK_PLUGIN_DIR/mcp-server.sh"

        plugin = PluginSchema(
            schema_version="2026-01-23",
            name="TestPlugin",
            description="Test plugin",
            mcp=McpConfig(transport="stdio", command=command),
        )

        # When
        result = generate_mcp_config(plugin, self.plugin_dir, "test-plugin")

        # Then
        expected_command = f"{self.plugin_dir.resolve()}/mcp-server.sh"
        assert result.config["test-plugin"]["command"] == expected_command

    def test_substitutes_args(self) -> None:
        """Verify args are substituted."""
        # Given
        command = "python"
        args = ["--config", "$ATK_PLUGIN_DIR/config.json", "--data-dir", "${ATK_PLUGIN_DIR}/data"]

        plugin = PluginSchema(
            schema_version="2026-01-23",
            name="TestPlugin",
            description="Test plugin",
            mcp=McpConfig(transport="stdio", command=command, args=args),
        )

        # When
        result = generate_mcp_config(plugin, self.plugin_dir, "test-plugin")

        # Then
        plugin_dir_str = str(self.plugin_dir.resolve())
        expected_args = [
            "--config",
            f"{plugin_dir_str}/config.json",
            "--data-dir",
            f"{plugin_dir_str}/data",
        ]
        assert result.config["test-plugin"]["args"] == expected_args

    def test_substitutes_working_dir(self) -> None:
        """Verify working_dir is substituted."""
        # Given
        command = "python"
        working_dir = "$ATK_PLUGIN_DIR/vendor"

        plugin = PluginSchema(
            schema_version="2026-01-23",
            name="TestPlugin",
            description="Test plugin",
            mcp=McpConfig(transport="stdio", command=command, working_dir=working_dir),
        )

        # When
        result = generate_mcp_config(plugin, self.plugin_dir, "test-plugin")

        # Then
        expected_cwd = f"{self.plugin_dir.resolve()}/vendor"
        assert result.config["test-plugin"]["cwd"] == expected_cwd

