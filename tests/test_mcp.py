"""Tests for MCP configuration generation."""

from io import StringIO
from pathlib import Path

import pytest
from rich.console import Console

from atk import exit_codes
from atk.claude_memory import (
    ATK_SECTION_BEGIN,
    ATK_SECTION_END,
    inject_skill_reference,
    remove_skill_reference,
)
from atk.cli import app
from atk.mcp import (
    McpConfig,
    StdioMcpConfig,
    format_mcp_plaintext,
    generate_mcp_config,
    substitute_plugin_dir,
)
from atk.mcp_agents import build_claude_mcp_config
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, EnvVarConfig, McpPluginConfig, PluginSchema


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
            mcp=McpPluginConfig(transport="stdio", command=command),
        )

        # When
        result = generate_mcp_config(plugin, self.plugin_dir, "test-plugin")

        # Then
        expected_command = f"{self.plugin_dir.resolve()}/mcp-server.sh"
        assert isinstance(result, StdioMcpConfig)
        assert result.command == expected_command

    def test_substitutes_args(self) -> None:
        """Verify args are substituted."""
        # Given
        command = "python"
        args = ["--config", "$ATK_PLUGIN_DIR/config.json", "--data-dir", "${ATK_PLUGIN_DIR}/data"]

        plugin = PluginSchema(
            schema_version="2026-01-23",
            name="TestPlugin",
            description="Test plugin",
            mcp=McpPluginConfig(transport="stdio", command=command, args=args),
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
        assert isinstance(result, StdioMcpConfig)
        assert result.args == expected_args


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
        mcp=McpPluginConfig(transport="stdio", command=command, args=args, env=mcp_env),
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
        mcp=McpPluginConfig(transport="sse", endpoint=endpoint, env=mcp_env),
        env_vars=env_vars or [],
    )


def _write_env_file(plugin_dir: Path, values: dict[str, str]) -> None:
    """Write a .env file into the plugin directory."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / ".env").write_text(
        "\n".join(f"{k}={v}" for k, v in values.items()) + "\n"
    )


def _render_plaintext(result: McpConfig) -> str:
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
    # Given
    var_name = "MODEL_PATH"
    default_value = "/opt/models/kokoro"
    plugin = _make_stdio_plugin(
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name, default=default_value)],
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()
    # No .env file written — var is absent

    # When
    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # Then
    assert result.env[var_name] == default_value
    assert var_name not in result.missing_vars


def test_generate_mcp_config_dotenv_value_takes_precedence_over_default(tmp_path: Path) -> None:
    """A value present in .env overrides the declared default in env_vars."""
    # Given
    var_name = "MODEL_PATH"
    default_value = "/opt/models/default"
    dotenv_value = "/home/user/custom-model"
    plugin = _make_stdio_plugin(
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name, default=default_value)],
    )
    plugin_dir = tmp_path / "test-plugin"
    _write_env_file(plugin_dir, {var_name: dotenv_value})

    # When
    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # Then
    assert result.env[var_name] == dotenv_value
    assert var_name not in result.missing_vars


def test_generate_mcp_config_marks_not_set_when_no_value_and_no_default(tmp_path: Path) -> None:
    """A var with no .env value and no declared default is marked <NOT_SET>."""
    # Given
    var_name = "API_KEY"
    plugin = _make_stdio_plugin(
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name)],  # no default
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    # When
    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # Then
    assert result.env[var_name] == "<NOT_SET>"
    assert var_name in result.missing_vars


# ---------------------------------------------------------------------------
# Env var substitution in command and args
# ---------------------------------------------------------------------------

def test_generate_mcp_config_substitutes_env_var_in_args(tmp_path: Path) -> None:
    """$VAR references in args are replaced with the resolved env var value.

    Regression: OpenMemory uses args=['-y', 'mcp-remote', '$OPENMEMORY_URL/mcp'].
    Claude Code spawns servers via execve (no shell), so $VAR in args is never
    expanded at runtime. ATK must substitute the resolved value before handing
    the config to any agent CLI.
    """
    # Given
    var_name = "OPENMEMORY_URL"
    var_value = "http://localhost:8787"
    plugin = _make_stdio_plugin(
        command="npx",
        args=["-y", "mcp-remote", f"${var_name}/mcp"],
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name, default=var_value)],
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    # When
    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # Then — $OPENMEMORY_URL/mcp must be replaced with the resolved URL
    assert isinstance(result, StdioMcpConfig)
    expected_args = ["-y", "mcp-remote", f"{var_value}/mcp"]
    assert result.args == expected_args


def test_generate_mcp_config_substitutes_braces_env_var_in_args(tmp_path: Path) -> None:
    """${VAR} brace syntax in args is also substituted."""
    # Given
    var_name = "BASE_URL"
    var_value = "http://localhost:9000"
    plugin = _make_stdio_plugin(
        command="npx",
        args=["--url", f"${{{var_name}}}/endpoint"],
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name, default=var_value)],
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    # When
    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # Then
    assert isinstance(result, StdioMcpConfig)
    expected_args = ["--url", f"{var_value}/endpoint"]
    assert result.args == expected_args


def test_generate_mcp_config_leaves_not_set_var_unexpanded_in_args(tmp_path: Path) -> None:
    """If a $VAR reference in args maps to a NOT_SET var, leave it unchanged."""
    # Given
    var_name = "MISSING_URL"
    plugin = _make_stdio_plugin(
        command="npx",
        args=["--url", f"${var_name}/mcp"],
        mcp_env=[var_name],
        env_vars=[EnvVarConfig(name=var_name)],  # no default
    )
    plugin_dir = tmp_path / "test-plugin"
    plugin_dir.mkdir()

    # When
    result = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # Then — unresolvable var stays as the literal $VAR string
    assert isinstance(result, StdioMcpConfig)
    assert result.args == ["--url", f"${var_name}/mcp"]
    assert var_name in result.missing_vars


# ---------------------------------------------------------------------------
# Formatter adapter layer — format_mcp_plaintext
# ---------------------------------------------------------------------------

def test_format_mcp_plaintext_stdio(tmp_path: Path) -> None:
    """stdio plugin: exact rendered output with Name, Command, and Environment Variables."""
    # Given
    command = "uv"
    args = ["run", "--directory", str(tmp_path / "plugin"), "server.py"]
    var_name = "API_KEY"
    var_value = "my-secret"
    plugin = _make_stdio_plugin(command=command, args=args, mcp_env=[var_name])
    plugin_dir = tmp_path / "plugin"
    _write_env_file(plugin_dir, {var_name: var_value})
    mcp_config = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # When
    rendered = _render_plaintext(mcp_config)

    # Then
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
    # Given
    endpoint = "http://localhost:8080/mcp"
    plugin = _make_sse_plugin(endpoint=endpoint)  # no env vars
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, "test-plugin")

    # When
    rendered = _render_plaintext(mcp_config)

    # Then
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
    # Given
    plugin_name = "TestPlugin"
    command = "uv"
    args = ["run", "server.py"]
    plugin = _make_stdio_plugin(name=plugin_name, command=command, args=args)
    create_plugin(plugin=plugin, directory="test-plugin")

    # When
    result = cli_runner.invoke(app, ["mcp", "test-plugin"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    assert "Name:" in result.output
    assert plugin_name in result.output
    assert "Command:" in result.output
    assert f"{command} {' '.join(args)}" in result.output



# ---------------------------------------------------------------------------
# build_claude_mcp_config — unit tests (pure, no subprocess)
# ---------------------------------------------------------------------------

def test_build_claude_mcp_config_stdio_minimal(tmp_path: Path) -> None:
    """Minimal stdio plugin: argv has correct shape with name and command."""
    # Given
    plugin_name = "my-plugin"
    command = "uv"
    plugin = _make_stdio_plugin(name=plugin_name, command=command)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then
    assert result.argv == ["claude", "mcp", "add", "--scope", "user", "--", plugin_name, command]


def test_build_claude_mcp_config_stdio_with_args(tmp_path: Path) -> None:
    """Stdio plugin with args: all args appended positionally after command."""
    # Given
    plugin_name = "my-plugin"
    command = "uv"
    plugin_args = ["run", "--directory", "/some/path", "server.py"]
    plugin = _make_stdio_plugin(name=plugin_name, command=command, args=plugin_args)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then
    assert result.argv == [
        "claude", "mcp", "add", "--scope", "user", "--",
        plugin_name, command, *plugin_args,
    ]


def test_build_claude_mcp_config_double_dash_terminates_option_parsing(tmp_path: Path) -> None:
    """-- must appear before server name so claude does not eat server args as its own options.

    Regression: `uv run --directory /path` caused `error: unknown option '--directory'`
    because claude's parser was still active when it hit --directory.
    """
    # Given
    plugin_name = "parley"
    command = "uv"
    plugin_args = ["run", "--directory", "/some/path", "parley-mcp", "run"]
    plugin = _make_stdio_plugin(name=plugin_name, command=command, args=plugin_args)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then — "--" must appear before the server name
    double_dash_idx = result.argv.index("--")
    name_idx = result.argv.index(plugin_name)
    assert double_dash_idx < name_idx
    # and --directory must survive intact in the argv
    assert "--directory" in result.argv



def test_build_claude_mcp_config_stdio_with_env_vars(tmp_path: Path) -> None:
    """Set env vars each become a separate -e KEY=VAL flag."""
    # Given
    plugin_name = "my-plugin"
    command = "uv"
    var_name = "API_KEY"
    var_value = "secret-123"
    plugin = _make_stdio_plugin(name=plugin_name, command=command, mcp_env=[var_name])
    plugin_dir = tmp_path / "plugin"
    _write_env_file(plugin_dir, {var_name: var_value})
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then
    assert result.argv == [
        "claude", "mcp", "add", "--scope", "user",
        "-e", f"{var_name}={var_value}",
        "--", plugin_name, command,
    ]


def test_build_claude_mcp_config_stdio_multiple_env_vars(tmp_path: Path) -> None:
    """Multiple env vars produce multiple consecutive -e KEY=VAL flags."""
    # Given
    plugin_name = "my-plugin"
    command = "uv"
    var1_name, var1_value = "API_KEY", "secret-123"
    var2_name, var2_value = "MODEL", "gpt-4"
    plugin = _make_stdio_plugin(
        name=plugin_name, command=command, mcp_env=[var1_name, var2_name]
    )
    plugin_dir = tmp_path / "plugin"
    _write_env_file(plugin_dir, {var1_name: var1_value, var2_name: var2_value})
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then
    assert result.argv == [
        "claude", "mcp", "add", "--scope", "user",
        "-e", f"{var1_name}={var1_value}",
        "-e", f"{var2_name}={var2_value}",
        "--", plugin_name, command,
    ]


def test_build_claude_mcp_config_stdio_skips_not_set_env_vars(tmp_path: Path) -> None:
    """Env vars with <NOT_SET> value are omitted from the argv entirely."""
    # Given
    plugin_name = "my-plugin"
    command = "uv"
    set_var_name, set_var_value = "MODEL", "gpt-4"
    missing_var_name = "API_KEY"
    plugin = _make_stdio_plugin(
        name=plugin_name, command=command,
        mcp_env=[set_var_name, missing_var_name],
        env_vars=[EnvVarConfig(name=missing_var_name)],
    )
    plugin_dir = tmp_path / "plugin"
    _write_env_file(plugin_dir, {set_var_name: set_var_value})
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then — missing var must not appear anywhere in the argv
    assert missing_var_name not in " ".join(result.argv)
    assert result.argv == [
        "claude", "mcp", "add", "--scope", "user",
        "-e", f"{set_var_name}={set_var_value}",
        "--", plugin_name, command,
    ]


def test_build_claude_mcp_config_sse(tmp_path: Path) -> None:
    """SSE plugin: --transport sse inserted and URL placed as positional."""
    # Given
    plugin_name = "my-plugin"
    endpoint = "http://localhost:8080/mcp"
    plugin = _make_sse_plugin(name=plugin_name, endpoint=endpoint)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then
    assert result.argv == [
        "claude", "mcp", "add", "--transport", "sse", "--scope", "user",
        "--", plugin_name, endpoint,
    ]


def test_build_claude_mcp_config_scope_defaults_to_user(tmp_path: Path) -> None:
    """Default scope is 'user' — --scope user always present when no scope given."""
    # Given
    plugin_name = "my-plugin"
    plugin = _make_stdio_plugin(name=plugin_name)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config)

    # Then
    scope_index = result.argv.index("--scope")
    assert result.argv[scope_index + 1] == "user"


def test_build_claude_mcp_config_custom_scope(tmp_path: Path) -> None:
    """Passing scope='local' produces --scope local in the argv."""
    # Given
    plugin_name = "my-plugin"
    custom_scope = "local"
    plugin = _make_stdio_plugin(name=plugin_name)
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    mcp_config = generate_mcp_config(plugin, plugin_dir, plugin_name)

    # When
    result = build_claude_mcp_config(mcp_config, scope=custom_scope)

    # Then
    scope_index = result.argv.index("--scope")
    assert result.argv[scope_index + 1] == custom_scope


# ---------------------------------------------------------------------------
# generate_mcp_config — fail-fast for missing transport-required fields
# ---------------------------------------------------------------------------

def test_generate_mcp_config_stdio_raises_when_command_missing(tmp_path: Path) -> None:
    """stdio transport with no command is a misconfiguration — raises ValueError immediately."""
    # Given
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    plugin = PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name="BrokenPlugin",
        description="missing command",
        mcp=McpPluginConfig(transport="stdio"),  # no command
    )

    # When / Then
    with pytest.raises(ValueError, match="no command"):
        generate_mcp_config(plugin, plugin_dir, "broken-plugin")


def test_generate_mcp_config_sse_raises_when_endpoint_missing(tmp_path: Path) -> None:
    """sse transport with no endpoint is a misconfiguration — raises ValueError immediately."""
    # Given
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    plugin = PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name="BrokenPlugin",
        description="missing endpoint",
        mcp=McpPluginConfig(transport="sse"),  # no endpoint
    )

    # When / Then
    with pytest.raises(ValueError, match="no endpoint"):
        generate_mcp_config(plugin, plugin_dir, "broken-plugin")


# ---------------------------------------------------------------------------
# inject_skill_reference / remove_skill_reference
# ---------------------------------------------------------------------------


class TestInjectSkillReference:
    """Tests for claude_memory.inject_skill_reference."""

    def test_creates_claude_md_when_missing(self, tmp_path: Path) -> None:
        """inject_skill_reference creates CLAUDE.md (and its parent dir) if absent."""
        # Given
        claude_md = tmp_path / ".claude" / "CLAUDE.md"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected is True
        assert claude_md.exists()
        content = claude_md.read_text()
        assert ATK_SECTION_BEGIN in content
        assert ATK_SECTION_END in content
        assert f"@{skill_path.resolve()}" in content

    def test_adds_atk_section_to_existing_file_without_section(self, tmp_path: Path) -> None:
        """inject_skill_reference appends ATK section to a CLAUDE.md that has user content."""
        # Given
        claude_md = tmp_path / "CLAUDE.md"
        user_content = "# My notes\n\nSome user content.\n"
        claude_md.write_text(user_content)
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected is True
        content = claude_md.read_text()
        # User content must be preserved
        assert "Some user content." in content
        # ATK section must follow it
        assert content.index(ATK_SECTION_BEGIN) > content.index("Some user content.")
        assert f"@{skill_path.resolve()}" in content

    def test_idempotent_when_reference_already_present(self, tmp_path: Path) -> None:
        """inject_skill_reference returns False and does not duplicate an existing reference."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "CLAUDE.md"

        inject_skill_reference(skill_path, claude_md_path=claude_md)  # first call

        # When
        injected_again = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected_again is False
        content = claude_md.read_text()
        reference = f"@{skill_path.resolve()}"
        assert content.count(reference) == 1

    def test_multiple_plugins_all_appear_in_section(self, tmp_path: Path) -> None:
        """Multiple plugins each get their own reference line inside the ATK section."""
        # Given
        claude_md = tmp_path / "CLAUDE.md"
        skill_a = tmp_path / "plugin-a" / "SKILL.md"
        skill_b = tmp_path / "plugin-b" / "SKILL.md"
        skill_a.parent.mkdir()
        skill_b.parent.mkdir()
        skill_a.write_text("# A")
        skill_b.write_text("# B")

        # When
        inject_skill_reference(skill_a, claude_md_path=claude_md)
        inject_skill_reference(skill_b, claude_md_path=claude_md)

        # Then
        content = claude_md.read_text()
        assert f"@{skill_a.resolve()}" in content
        assert f"@{skill_b.resolve()}" in content
        # Both must be inside the ATK section
        begin = content.index(ATK_SECTION_BEGIN)
        end = content.index(ATK_SECTION_END)
        section = content[begin:end]
        assert f"@{skill_a.resolve()}" in section
        assert f"@{skill_b.resolve()}" in section

    def test_references_outside_atk_section_are_not_deduplicated(self, tmp_path: Path) -> None:
        """A reference that the user placed outside the ATK section does not block injection."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        reference = f"@{skill_path.resolve()}"
        claude_md = tmp_path / "CLAUDE.md"
        # User manually placed the reference outside any ATK section
        claude_md.write_text(f"{reference}\n")

        # When
        injected = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then — ATK still adds its own managed reference inside the section
        assert injected is True
        content = claude_md.read_text()
        assert ATK_SECTION_BEGIN in content


class TestRemoveSkillReference:
    """Tests for claude_memory.remove_skill_reference."""

    def test_removes_existing_reference(self, tmp_path: Path) -> None:
        """remove_skill_reference removes a reference previously added by inject."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "CLAUDE.md"
        inject_skill_reference(skill_path, claude_md_path=claude_md)

        # When
        removed = remove_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert removed is True
        content = claude_md.read_text()
        assert f"@{skill_path.resolve()}" not in content

    def test_returns_false_when_not_present(self, tmp_path: Path) -> None:
        """remove_skill_reference returns False when the reference does not exist."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(f"{ATK_SECTION_BEGIN}\n{ATK_SECTION_END}\n")

        # When
        removed = remove_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert removed is False

    def test_returns_false_when_claude_md_missing(self, tmp_path: Path) -> None:
        """remove_skill_reference returns False gracefully when CLAUDE.md does not exist."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "nonexistent" / "CLAUDE.md"

        # When
        removed = remove_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert removed is False
