"""Plug/unplug orchestration — wire plugins into coding agents.

Adapts to what a plugin offers: MCP registration, skill injection, or both.
Reuses all agent runners and skill injectors from ``atk.commands.mcp``.
"""

from __future__ import annotations

from pathlib import Path

from atk import cli_logger, exit_codes
from atk.commands.mcp import (
    AgentStatus,
    inject_auggie_skill_md,
    inject_claude_skill_md,
    inject_codex_skill_md,
    inject_gemini_skill_md,
    inject_opencode_skill_md,
    print_agent_summary,
    remove_auggie_skill_md,
    remove_claude_skill_md,
    remove_cli_agent_by_name,
    remove_codex_skill_md,
    remove_file_agent,
    remove_gemini_skill_md,
    remove_opencode_skill_md,
    run_cli_agent,
    run_file_agent,
)
from atk.mcp import generate_mcp_config
from atk.mcp_agents import (
    build_auggie_mcp_config,
    build_claude_mcp_config,
    build_codex_mcp_config,
    build_gemini_mcp_config,
    build_opencode_mcp_config,
)
from atk.mcp_configure import (
    run_auggie_mcp_add,
    run_auggie_mcp_remove,
    run_claude_mcp_add,
    run_claude_mcp_remove,
    run_codex_mcp_add,
    run_codex_mcp_remove,
    run_gemini_mcp_add,
    run_gemini_mcp_remove,
)
from atk.plugin_schema import PluginSchema


def plug_plugin(
    plugin_schema: PluginSchema,
    plugin_dir: Path,
    *,
    claude: bool = False,
    codex: bool = False,
    gemini: bool = False,
    auggie: bool = False,
    opencode: bool = False,
    force: bool = False,
) -> int:
    """Wire a plugin into one or more coding agents.

    Adapts to what the plugin offers:
    - MCP + SKILL.md → register MCP server + inject skill
    - MCP only → register MCP server
    - SKILL.md only → inject skill
    - Neither → return PLUGIN_INVALID exit code

    Returns an exit code (0 for success, non-zero for failure).
    """
    has_mcp = plugin_schema.mcp is not None
    has_skill = (plugin_dir / "SKILL.md").exists()

    if not has_mcp and not has_skill:
        cli_logger.error(
            f"Nothing to plug — plugin '{plugin_schema.name}' has no MCP config or SKILL.md"
        )
        return exit_codes.PLUGIN_INVALID

    # Generate MCP config only when the plugin has one.
    result = None
    if has_mcp:
        result = generate_mcp_config(plugin_schema, plugin_dir, plugin_schema.name)
        for var in result.missing_vars:
            cli_logger.warning(f"Environment variable '{var}' is not set")

    outcomes: list[tuple[str, AgentStatus, str]] = []

    if claude:
        if has_mcp and result is not None:
            status, detail = run_cli_agent(
                "Claude Code", build_claude_mcp_config(result), "claude",
                run_claude_mcp_add, force=force,
            )
            outcomes.append(("Claude Code", status, detail))
            if status == "configured":
                inject_claude_skill_md(plugin_dir, force=force)
        else:
            inject_claude_skill_md(plugin_dir, force=force)
            outcomes.append(("Claude Code", "configured", "skill only"))

    if codex:
        if has_mcp and result is not None:
            status, detail = run_cli_agent(
                "Codex", build_codex_mcp_config(result), "codex",
                run_codex_mcp_add, force=force,
            )
            outcomes.append(("Codex", status, detail))
            if status == "configured":
                inject_codex_skill_md(plugin_schema.name, plugin_dir, force=force)
        else:
            inject_codex_skill_md(plugin_schema.name, plugin_dir, force=force)
            outcomes.append(("Codex", "configured", "skill only"))

    if gemini:
        if has_mcp and result is not None:
            status, detail = run_cli_agent(
                "Gemini CLI", build_gemini_mcp_config(result), "gemini",
                run_gemini_mcp_add, force=force,
            )
            outcomes.append(("Gemini CLI", status, detail))
            if status == "configured":
                inject_gemini_skill_md(plugin_dir, force=force)
        else:
            inject_gemini_skill_md(plugin_dir, force=force)
            outcomes.append(("Gemini CLI", "configured", "skill only"))

    if auggie:
        if has_mcp and result is not None:
            status, detail = run_cli_agent(
                "Auggie", build_auggie_mcp_config(result), "auggie",
                run_auggie_mcp_add, force=force,
            )
            outcomes.append(("Auggie", status, detail))
            if status == "configured":
                inject_auggie_skill_md(plugin_dir, force=force)
        else:
            inject_auggie_skill_md(plugin_dir, force=force)
            outcomes.append(("Auggie", "configured", "skill only"))

    if opencode:
        if has_mcp and result is not None:
            status, detail = run_file_agent(
                "OpenCode", build_opencode_mcp_config(result), force=force,
            )
            outcomes.append(("OpenCode", status, detail))
            if status == "configured":
                inject_opencode_skill_md(plugin_dir, force=force)
        else:
            inject_opencode_skill_md(plugin_dir, force=force)
            outcomes.append(("OpenCode", "configured", "skill only"))

    print_agent_summary(outcomes)

    has_failures = any(s in ("failed", "not_found") for _, s, _ in outcomes)
    return exit_codes.GENERAL_ERROR if has_failures else exit_codes.SUCCESS


def unplug_plugin(
    plugin_schema: PluginSchema,
    plugin_dir: Path,
    *,
    claude: bool = False,
    codex: bool = False,
    gemini: bool = False,
    auggie: bool = False,
    opencode: bool = False,
    force: bool = False,
) -> int:
    """Remove a plugin's wiring from one or more coding agents.

    Adapts to what the plugin offers: removes MCP registration, skill
    references, or both.

    Returns an exit code (0 for success, non-zero for failure).
    """
    has_mcp = plugin_schema.mcp is not None

    outcomes: list[tuple[str, AgentStatus, str]] = []

    if claude:
        if has_mcp:
            status, detail = remove_cli_agent_by_name(
                "Claude Code", plugin_schema.name, "claude",
                run_claude_mcp_remove, force=force,
            )
            outcomes.append(("Claude Code", status, detail))
            if status == "removed":
                remove_claude_skill_md(plugin_dir)
        else:
            remove_claude_skill_md(plugin_dir)
            outcomes.append(("Claude Code", "removed", "skill only"))

    if codex:
        if has_mcp:
            status, detail = remove_cli_agent_by_name(
                "Codex", plugin_schema.name, "codex",
                run_codex_mcp_remove, force=force,
            )
            outcomes.append(("Codex", status, detail))
            if status == "removed":
                remove_codex_skill_md(plugin_schema.name, plugin_dir)
        else:
            remove_codex_skill_md(plugin_schema.name, plugin_dir)
            outcomes.append(("Codex", "removed", "skill only"))

    if gemini:
        if has_mcp:
            status, detail = remove_cli_agent_by_name(
                "Gemini CLI", plugin_schema.name, "gemini",
                run_gemini_mcp_remove, force=force,
            )
            outcomes.append(("Gemini CLI", status, detail))
            if status == "removed":
                remove_gemini_skill_md(plugin_dir)
        else:
            remove_gemini_skill_md(plugin_dir)
            outcomes.append(("Gemini CLI", "removed", "skill only"))

    if auggie:
        if has_mcp:
            status, detail = remove_cli_agent_by_name(
                "Auggie", plugin_schema.name, "auggie",
                run_auggie_mcp_remove, force=force,
            )
            outcomes.append(("Auggie", status, detail))
            if status == "removed":
                remove_auggie_skill_md(plugin_dir)
        else:
            remove_auggie_skill_md(plugin_dir)
            outcomes.append(("Auggie", "removed", "skill only"))

    if opencode:
        if has_mcp:
            status, detail = remove_file_agent(
                "OpenCode", plugin_schema.name, plugin_dir,
                force=force,
            )
            outcomes.append(("OpenCode", status, detail))
        else:
            remove_opencode_skill_md(plugin_schema.name, plugin_dir)
            outcomes.append(("OpenCode", "removed", "skill only"))

    print_agent_summary(outcomes)

    has_failures = any(s in ("failed", "not_found") for _, s, _ in outcomes)
    return exit_codes.GENERAL_ERROR if has_failures else exit_codes.SUCCESS
