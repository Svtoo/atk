"""MCP agent add/remove orchestration and skill-injection helpers.

Contains the per-agent registration/unregistration runners and the
SKILL.md injection/removal helpers for all supported coding agents.
"""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from rich.console import Console

from atk import cli_logger
from atk.agents.auggie_skill import inject_skill_symlink, remove_skill_symlink
from atk.agents.claude_skill import inject_skill_reference, remove_skill_reference
from atk.agents.codex_skill import inject_skill_directive, remove_skill_directive
from atk.agents.opencode_skill import inject_skill_instruction, remove_opencode_plugin
from atk.commands.preconditions import stdin_prompt
from atk.mcp_agents import AgentMcpConfig, OpenCodeMcpConfig
from atk.mcp_configure import run_opencode_mcp_add

console = Console()

# Status values returned by all agent runner functions.
AgentStatus = Literal["configured", "removed", "skipped", "not_found", "failed"]

# ---------------------------------------------------------------------------
# Agent add helpers
# ---------------------------------------------------------------------------


def run_cli_agent(
    label: str,
    agent_config: AgentMcpConfig,
    executable_name: str,
    run_fn: Callable[[AgentMcpConfig], int],
    force: bool = False,
) -> tuple[AgentStatus, str]:
    """Confirm and execute a CLI-based MCP agent registration.

    Returns:
        (status, detail) where status ∈ {configured, skipped, not_found, failed}.
    """
    console.print(f"\n[{label}] Will run:\n  {' '.join(agent_config.argv)}\n")
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return "skipped", ""
    try:
        code = run_fn(agent_config)
    except FileNotFoundError:
        return "not_found", f"'{executable_name}' not found on PATH"
    if code != 0:
        return "failed", f"exit code {code}"
    return "configured", ""


def run_file_agent(
    label: str, agent_config: OpenCodeMcpConfig, *, force: bool = False
) -> tuple[AgentStatus, str]:
    """Confirm and execute a file-based MCP agent registration (OpenCode).

    Returns:
        (status, detail) where status ∈ {configured, skipped, failed}.
    """
    preview = json.dumps({agent_config.entry_key: agent_config.entry_value}, indent=2)
    console.print(f"\n[{label}] Will add to {agent_config.file_path}:\n{preview}\n")
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return "skipped", ""
    try:
        run_opencode_mcp_add(agent_config)
    except (ValueError, OSError) as exc:
        return "failed", str(exc)
    return "configured", ""


# ---------------------------------------------------------------------------
# Agent remove helpers
# ---------------------------------------------------------------------------


def remove_cli_agent_by_name(
    label: str,
    plugin_name: str,
    executable_name: str,
    run_fn: Callable[[str], int],
    *,
    force: bool = False,
) -> tuple[AgentStatus, str]:
    """Confirm and execute a CLI-based MCP agent removal.

    Returns:
        (status, detail) where status ∈ {removed, skipped, not_found, failed}.
    """
    argv_preview = f"{executable_name} mcp remove {plugin_name}"
    console.print(f"\n[{label}] Will run:\n  {argv_preview}\n")
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return "skipped", ""
    try:
        code = run_fn(plugin_name)
    except FileNotFoundError:
        return "not_found", f"'{executable_name}' not found on PATH"
    if code != 0:
        return "failed", f"exit code {code}"
    return "removed", ""


def remove_file_agent(
    label: str,
    plugin_name: str,
    plugin_dir: Path,
    *,
    force: bool = False,
) -> tuple[AgentStatus, str]:
    """Confirm and execute a file-based MCP agent removal (OpenCode).

    Returns:
        (status, detail) where status ∈ {removed, skipped, failed}.
    """
    console.print(
        f"\n[{label}] Will remove MCP entry '{plugin_name}' "
        f"and SKILL.md reference from opencode.jsonc\n"
    )
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return "skipped", ""
    remove_opencode_skill_md(plugin_name, plugin_dir)
    return "removed", ""


# ---------------------------------------------------------------------------
# Skill injection helpers (add flow)
# ---------------------------------------------------------------------------


def inject_claude_skill_md(plugin_dir: Path, *, force: bool = False) -> None:
    """Offer to inject the plugin's SKILL.md into ~/.claude/CLAUDE.md."""
    skill_path = plugin_dir / "SKILL.md"
    if not skill_path.exists():
        return
    console.print(f"\n[Claude Code] Will add to ~/.claude/CLAUDE.md:\n  @{skill_path.resolve()}\n")
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return
    injected = inject_skill_reference(skill_path)
    if injected:
        cli_logger.success("Added SKILL.md to ~/.claude/CLAUDE.md")
    else:
        cli_logger.info("SKILL.md already referenced in ~/.claude/CLAUDE.md")


def inject_auggie_skill_md(plugin_dir: Path, *, force: bool = False) -> None:
    """Offer to inject the plugin's SKILL.md as a symlink in ~/.augment/rules/."""
    skill_path = plugin_dir / "SKILL.md"
    if not skill_path.exists():
        return
    symlink_name = f"atk-{plugin_dir.name}.md"
    console.print(
        f"\n[Auggie] Will create symlink:\n"
        f"  ~/.augment/rules/{symlink_name} → {skill_path.resolve()}\n"
    )
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return
    try:
        injected = inject_skill_symlink(plugin_dir.name, skill_path)
    except FileExistsError:
        cli_logger.error(
            f"~/.augment/rules/{symlink_name} exists and is not a symlink managed by ATK"
        )
        return
    if injected:
        cli_logger.success(f"Created skill symlink ~/.augment/rules/{symlink_name}")
    else:
        cli_logger.info(f"Skill symlink ~/.augment/rules/{symlink_name} already up to date")


def inject_codex_skill_md(plugin_name: str, plugin_dir: Path, *, force: bool = False) -> None:
    """Offer to inject the plugin's SKILL.md read-directive into ~/.codex/AGENTS.md."""
    skill_path = plugin_dir / "SKILL.md"
    if not skill_path.exists():
        return
    console.print(
        f"\n[Codex] Will add read-directive to ~/.codex/AGENTS.md:\n"
        f"  Read {skill_path.resolve()} for instructions on using the {plugin_name} MCP tools.\n"
    )
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return
    injected = inject_skill_directive(plugin_name, skill_path)
    if injected:
        cli_logger.success("Added SKILL.md read-directive to ~/.codex/AGENTS.md")
    else:
        cli_logger.info("SKILL.md read-directive already present in ~/.codex/AGENTS.md")


def inject_opencode_skill_md(plugin_dir: Path, *, force: bool = False) -> None:
    """Offer to add the plugin's SKILL.md to opencode.jsonc instructions array."""
    skill_path = plugin_dir / "SKILL.md"
    if not skill_path.exists():
        return
    resolved = skill_path.resolve()
    console.print(f"\n[OpenCode] Will add to opencode.jsonc instructions:\n  {resolved}\n")
    if not force and stdin_prompt("Proceed? [y/N] ").strip().lower() != "y":
        return
    injected = inject_skill_instruction(skill_path)
    if injected:
        cli_logger.success("Added SKILL.md to opencode.jsonc instructions")
    else:
        cli_logger.info("SKILL.md already present in opencode.jsonc instructions")


# ---------------------------------------------------------------------------
# Skill removal helpers (remove flow)
# ---------------------------------------------------------------------------


def remove_claude_skill_md(plugin_dir: Path) -> None:
    """Remove the plugin's SKILL.md reference from ~/.claude/CLAUDE.md."""
    skill_path = plugin_dir / "SKILL.md"
    if not skill_path.exists():
        return
    removed = remove_skill_reference(skill_path)
    if removed:
        cli_logger.success("Removed SKILL.md reference from ~/.claude/CLAUDE.md")
    else:
        cli_logger.info("SKILL.md reference not found in ~/.claude/CLAUDE.md")


def remove_auggie_skill_md(plugin_dir: Path) -> None:
    """Remove the plugin's SKILL.md symlink from ~/.augment/rules/."""
    symlink_name = f"atk-{plugin_dir.name}.md"
    removed = remove_skill_symlink(plugin_dir.name)
    if removed:
        cli_logger.success(f"Removed skill symlink ~/.augment/rules/{symlink_name}")
    else:
        cli_logger.info(f"Skill symlink ~/.augment/rules/{symlink_name} not found")


def remove_codex_skill_md(plugin_name: str, plugin_dir: Path) -> None:
    """Remove the plugin's SKILL.md read-directive from ~/.codex/AGENTS.md."""
    skill_path = plugin_dir / "SKILL.md"
    if not skill_path.exists():
        return
    removed = remove_skill_directive(plugin_name, skill_path)
    if removed:
        cli_logger.success("Removed SKILL.md read-directive from ~/.codex/AGENTS.md")
    else:
        cli_logger.info("SKILL.md read-directive not found in ~/.codex/AGENTS.md")


def remove_opencode_skill_md(plugin_name: str, plugin_dir: Path) -> None:
    """Remove the plugin's SKILL.md from opencode.jsonc and its MCP entry.

    OpenCode removal is a single-file operation: both the MCP entry and the
    skill instruction are removed in one write via remove_opencode_plugin.
    """
    skill_path = plugin_dir / "SKILL.md"
    skill_path_arg = skill_path if skill_path.exists() else None
    mcp_removed, skill_removed = remove_opencode_plugin(plugin_name, skill_path_arg)
    if mcp_removed:
        cli_logger.success(f"Removed MCP entry '{plugin_name}' from opencode.jsonc")
    else:
        cli_logger.info(f"MCP entry '{plugin_name}' not found in opencode.jsonc")
    if skill_removed:
        cli_logger.success("Removed SKILL.md from opencode.jsonc instructions")
    elif skill_path_arg is not None:
        cli_logger.info("SKILL.md not found in opencode.jsonc instructions")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


def print_agent_summary(outcomes: list[tuple[str, AgentStatus, str]]) -> None:
    """Print per-agent outcome summary.

    Works for both add and remove flows.  Success statuses (``configured``,
    ``removed``) are shown as success; ``skipped`` as info; everything else
    as error.
    """
    console.print()
    for label, status, detail in outcomes:
        if status in ("configured", "removed"):
            cli_logger.success(f"[{label}] {status.capitalize()}")
        elif status == "skipped":
            cli_logger.info(f"[{label}] Skipped")
        elif status == "not_found":
            cli_logger.error(f"[{label}] Not found — {detail}")
        else:
            cli_logger.error(f"[{label}] Failed — {detail}")

