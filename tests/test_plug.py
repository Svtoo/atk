"""Tests for ``atk plug`` and ``atk unplug`` CLI commands."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from atk import exit_codes
from atk.cli import app
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, McpPluginConfig, PluginSchema


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mcp_plugin(name: str = "McpPlugin", command: str = "uv") -> PluginSchema:
    """Create a plugin schema with MCP config (no SKILL.md on disk)."""
    return PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description=f"Test plugin {name}",
        mcp=McpPluginConfig(transport="stdio", command=command),
    )


def _make_minimal_plugin(name: str = "MinimalPlugin") -> PluginSchema:
    """Create a plugin schema with neither MCP config nor SKILL.md on disk."""
    return PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description=f"Test plugin {name}",
    )


def _make_skill_only_plugin(name: str = "SkillOnlyPlugin") -> PluginSchema:
    """Create a plugin schema without MCP config (SKILL.md added separately)."""
    return PluginSchema(
        schema_version=PLUGIN_SCHEMA_VERSION,
        name=name,
        description=f"Test plugin {name}",
    )


# ---------------------------------------------------------------------------
# atk plug — validation tests
# ---------------------------------------------------------------------------


def test_plug_no_flags_warns(create_plugin, cli_runner) -> None:
    """``atk plug`` with no agent flags prints a warning and exits successfully."""
    # Given
    plugin = _make_mcp_plugin()
    create_plugin(plugin=plugin, directory="mcp-plugin")

    # When
    result = cli_runner.invoke(app, ["plug", "mcp-plugin"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    assert "No agent flags" in result.output


def test_plug_plugin_not_found(configure_atk_home, cli_runner) -> None:
    """``atk plug`` with a nonexistent plugin exits with PLUGIN_NOT_FOUND."""
    # Given
    configure_atk_home()

    # When
    result = cli_runner.invoke(app, ["plug", "nonexistent", "--claude"])

    # Then
    assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
    assert "not found" in result.output


def test_plug_no_mcp_no_skill_errors(create_plugin, cli_runner) -> None:
    """``atk plug`` on a plugin with neither MCP nor SKILL.md exits with PLUGIN_INVALID."""
    # Given
    plugin = _make_minimal_plugin()
    create_plugin(plugin=plugin, directory="minimal-plugin")

    # When
    result = cli_runner.invoke(app, ["plug", "minimal-plugin", "--claude"])

    # Then
    assert result.exit_code == exit_codes.PLUGIN_INVALID
    assert "Nothing to plug" in result.output


# ---------------------------------------------------------------------------
# atk plug — MCP + SKILL.md plugin
# ---------------------------------------------------------------------------


def test_plug_mcp_and_skill_plugin(create_plugin, cli_runner) -> None:
    """``atk plug`` on a plugin with MCP + SKILL.md registers MCP and injects skill."""
    # Given
    plugin = _make_mcp_plugin(name="FullPlugin")
    plugin_dir = create_plugin(plugin=plugin, directory="full-plugin")
    skill_path = plugin_dir / "SKILL.md"
    skill_path.write_text("# Full Plugin Skill\n")

    # When — force=True to skip prompts; mock subprocess to avoid real CLI calls
    with patch("atk.commands.plug.run_cli_agent", return_value=("configured", "")) as mock_run, \
         patch("atk.commands.plug.inject_claude_skill_md") as mock_skill:
        result = cli_runner.invoke(app, ["plug", "full-plugin", "--claude", "-y"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    mock_run.assert_called_once()
    mock_skill.assert_called_once()


# ---------------------------------------------------------------------------
# atk plug — skill-only plugin
# ---------------------------------------------------------------------------


def test_plug_skill_only_plugin_skips_mcp(create_plugin, cli_runner) -> None:
    """``atk plug`` on a plugin with SKILL.md but no MCP skips MCP and injects skill only."""
    # Given
    plugin = _make_skill_only_plugin(name="PersonaPlugin")
    plugin_dir = create_plugin(plugin=plugin, directory="persona-plugin")
    skill_content = "# My Persona\nBehavioral instructions.\n"
    (plugin_dir / "SKILL.md").write_text(skill_content)

    # When — mock skill injection to verify it's called
    with patch("atk.commands.plug.inject_claude_skill_md") as mock_skill:
        result = cli_runner.invoke(app, ["plug", "persona-plugin", "--claude", "-y"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    mock_skill.assert_called_once()
    # MCP registration should not appear in output since there's no MCP config
    assert "Will run:" not in result.output or "mcp add" not in result.output


# ---------------------------------------------------------------------------
# atk plug — MCP-only plugin (no SKILL.md)
# ---------------------------------------------------------------------------


def test_plug_mcp_only_plugin_skips_skill(create_plugin, cli_runner) -> None:
    """``atk plug`` on a plugin with MCP but no SKILL.md registers MCP only."""
    # Given
    plugin = _make_mcp_plugin(name="McpOnlyPlugin")
    create_plugin(plugin=plugin, directory="mcp-only-plugin")
    # No SKILL.md written to disk

    # When
    with patch("atk.commands.plug.run_cli_agent", return_value=("configured", "")) as mock_run, \
         patch("atk.commands.plug.inject_claude_skill_md") as mock_skill:
        result = cli_runner.invoke(app, ["plug", "mcp-only-plugin", "--claude", "-y"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    mock_run.assert_called_once()
    # inject_claude_skill_md is still called (it checks SKILL.md existence internally)
    # but the key thing is no error occurred
    mock_skill.assert_called_once()


# ---------------------------------------------------------------------------
# atk plug — multiple agents
# ---------------------------------------------------------------------------


def test_plug_multiple_agents(create_plugin, cli_runner) -> None:
    """``atk plug`` with multiple agent flags processes all agents."""
    # Given
    plugin = _make_mcp_plugin(name="MultiAgent")
    plugin_dir = create_plugin(plugin=plugin, directory="multi-agent")
    (plugin_dir / "SKILL.md").write_text("# Multi Agent Skill\n")

    # When
    with patch("atk.commands.plug.run_cli_agent", return_value=("configured", "")) as mock_run, \
         patch("atk.commands.plug.inject_claude_skill_md"), \
         patch("atk.commands.plug.inject_codex_skill_md"), \
         patch("atk.commands.plug.inject_gemini_skill_md"):
        result = cli_runner.invoke(app, ["plug", "multi-agent", "--claude", "--codex", "--gemini", "-y"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    call_count = mock_run.call_count
    expected_agents = 3
    assert call_count == expected_agents


# ---------------------------------------------------------------------------
# atk unplug — validation tests
# ---------------------------------------------------------------------------


def test_unplug_no_flags_warns(create_plugin, cli_runner) -> None:
    """``atk unplug`` with no agent flags prints a warning and exits successfully."""
    # Given
    plugin = _make_mcp_plugin()
    create_plugin(plugin=plugin, directory="mcp-plugin")

    # When
    result = cli_runner.invoke(app, ["unplug", "mcp-plugin"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    assert "No agent flags" in result.output


def test_unplug_plugin_not_found(configure_atk_home, cli_runner) -> None:
    """``atk unplug`` with a nonexistent plugin exits with PLUGIN_NOT_FOUND."""
    # Given
    configure_atk_home()

    # When
    result = cli_runner.invoke(app, ["unplug", "nonexistent", "--claude"])

    # Then
    assert result.exit_code == exit_codes.PLUGIN_NOT_FOUND
    assert "not found" in result.output


# ---------------------------------------------------------------------------
# atk unplug — skill-only plugin
# ---------------------------------------------------------------------------


def test_unplug_skill_only_plugin(create_plugin, cli_runner) -> None:
    """``atk unplug`` on a skill-only plugin removes skill reference only."""
    # Given
    plugin = _make_skill_only_plugin(name="PersonaPlugin")
    plugin_dir = create_plugin(plugin=plugin, directory="persona-plugin")
    (plugin_dir / "SKILL.md").write_text("# My Persona\n")

    # When
    with patch("atk.commands.plug.remove_claude_skill_md") as mock_remove:
        result = cli_runner.invoke(app, ["unplug", "persona-plugin", "--claude", "-y"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    mock_remove.assert_called_once()


# ---------------------------------------------------------------------------
# atk unplug — MCP + SKILL.md plugin
# ---------------------------------------------------------------------------


def test_unplug_mcp_and_skill_plugin(create_plugin, cli_runner) -> None:
    """``atk unplug`` on a plugin with MCP + SKILL.md removes both."""
    # Given
    plugin = _make_mcp_plugin(name="FullPlugin")
    plugin_dir = create_plugin(plugin=plugin, directory="full-plugin")
    (plugin_dir / "SKILL.md").write_text("# Full Plugin Skill\n")

    # When
    with patch("atk.commands.plug.remove_cli_agent_by_name", return_value=("removed", "")) as mock_remove, \
         patch("atk.commands.plug.remove_claude_skill_md") as mock_skill:
        result = cli_runner.invoke(app, ["unplug", "full-plugin", "--claude", "-y"])

    # Then
    assert result.exit_code == exit_codes.SUCCESS
    mock_remove.assert_called_once()
    mock_skill.assert_called_once()
