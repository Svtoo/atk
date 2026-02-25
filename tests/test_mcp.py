"""Tests for MCP configuration generation."""

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from atk import exit_codes
from atk.cli import app
from atk.mcp import (
    McpConfigResult,
    format_mcp_plaintext,
    generate_mcp_config,
    substitute_plugin_dir,
)
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, EnvVarConfig, McpConfig, PluginSchema


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


# ---------------------------------------------------------------------------
# Helpers — module-level factory functions (not fixtures)
# ---------------------------------------------------------------------------

def _make_stdio_plugin(
    *,
    name: str = "TestPlugin",
    command: str = "uv",
    args: list[str] | None = None,
    mcp_env: list[str] | None = None,
    env_vars: list[EnvVarConfig] | None = None,
) -> PluginSchema:
    """Build a PluginSchema with a stdio MCP config."""
    return PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description="Test plugin",
        mcp=McpConfig(transport="stdio", command=command, args=args, env=mcp_env),
        env_vars=env_vars or [],
    )


def _make_sse_plugin(
    *,
    name: str = "TestPlugin",
    endpoint: str = "http://localhost:8080/mcp",
    mcp_env: list[str] | None = None,
    env_vars: list[EnvVarConfig] | None = None,
) -> PluginSchema:
    """Build a PluginSchema with an SSE MCP config."""
    return PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description="Test plugin",
        mcp=McpConfig(transport="sse", endpoint=endpoint, env=mcp_env),
        env_vars=env_vars or [],
    )


def _write_env_file(plugin_dir: Path, values: dict[str, str]) -> None:
    """Write a .env file into the plugin directory."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / ".env").write_text(
        "\n".join(f"{k}={v}" for k, v in values.items()) + "\n"
    )


def _render_plaintext(result: McpConfigResult) -> str:
    """Render format_mcp_plaintext() output as plain text (markup stripped)."""
    sio = StringIO()
    console = Console(file=sio, no_color=True, highlight=False, markup=True, width=1000)
    console.print(format_mcp_plaintext(result))
    return sio.getvalue()


# ---------------------------------------------------------------------------
# Data layer — env var default resolution (generate_mcp_config)
# ---------------------------------------------------------------------------

def test_generate_mcp_config_uses_env_var_default_when_not_in_dotenv(tmp_path: Path) -> None:
    """When a var is missing from .env but has a default in env_vars, use the default."""
    var_name = "MODEL_PATH"
    default_value = "/opt/models/kokoro"

    plugin = _make_stdio_plugin(
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name, default=default_value)],
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    # No .env file written — var is absent

    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    assert result.config["test-plugin"]["env"][var_name] == default_value
    assert var_name not in result.missing_vars


def test_generate_mcp_config_dotenv_value_takes_precedence_over_default(tmp_path: Path) -> None:
    """A value present in .env overrides the declared default in env_vars."""
    var_name = "MODEL_PATH"
    default_value = "/opt/models/default"
    dotenv_value = "/home/user/custom-model"

    plugin = _make_stdio_plugin(
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name, default=default_value)],
    )
    plugin_dir = tmp_path / "test-plugin"
    _write_env_file(plugin_dir, {var_name: dotenv_value})

    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    assert result.config["test-plugin"]["env"][var_name] == dotenv_value
    assert var_name not in result.missing_vars


def test_generate_mcp_config_marks_not_set_when_no_value_and_no_default(tmp_path: Path) -> None:
    """A var with no .env value and no declared default is marked <NOT_SET>."""
    var_name = "API_KEY"

    plugin = _make_stdio_plugin(
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name)],  # no default
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    assert result.config["test-plugin"]["env"][var_name] == "<NOT_SET>"
    assert var_name in result.missing_vars


# ---------------------------------------------------------------------------
# Formatter adapter layer — format_mcp_plaintext
# ---------------------------------------------------------------------------

def test_format_mcp_plaintext_stdio(tmp_path: Path) -> None:
    """stdio plugin: exact rendered output with Name, Command, and Environment Variables."""
    command = "uv"
    args = ["run", "--directory", str(tmp_path / "plugin"), "server.py"]
    var_name = "API_KEY"
    var_value = "my-secret"

    plugin = _make_stdio_plugin(command=command, args=args, mcp_env=[var_name])
    plugin_dir = tmp_path / "plugin"
    _write_env_file(plugin_dir, {var_name: var_value})

    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")
    rendered = _render_plaintext(result)

    expected = (
        f"Name:    {plugin.name}\n"
        f"Command:  {command} {' '.join(args)}\n"
        f"\n"
        f"Environment Variables:\n"
        f"  {var_name}={var_value}\n"
    )
    assert rendered == expected


def test_format_mcp_plaintext_sse(tmp_path: Path) -> None:
    """SSE plugin: exact rendered output with Name and URL; no Environment Variables section."""
    endpoint = "http://localhost:8080/mcp"

    plugin = _make_sse_plugin(endpoint=endpoint)  # no env vars
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")
    rendered = _render_plaintext(result)

    expected = (
        f"Name:    {plugin.name}\n"
        f"URL:     {endpoint}\n"
    )
    assert rendered == expected


# ---------------------------------------------------------------------------
# CLI E2E tests
# ---------------------------------------------------------------------------

def test_mcp_command_default_outputs_plaintext(create_plugin, cli_runner) -> None:
    """Default output (no --json) is plaintext with Name and Command sections."""
    plugin_name = "TestPlugin"
    command = "uv"
    args = ["run", "server.py"]

    plugin = _make_stdio_plugin(
        name=plugin_name,
        command=command,
        args=args,
    )
    create_plugin(plugin=plugin, directory="test-plugin")

    result = cli_runner.invoke(app, ["mcp", "test-plugin"])

    assert result.exit_code == exit_codes.SUCCESS
    assert "Name:" in result.output
    assert plugin_name in result.output
    assert "Command:" in result.output
    assert f"{command} {' '.join(args)}" in result.output
