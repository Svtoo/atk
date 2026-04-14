"""Status table rendering for the `atk status` command."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.table import Table

from atk.git import (
    git_ahead_behind,
    git_get_branch,
    git_get_remote_url,
    git_last_commit_info,
    git_working_dir_status,
)
from atk.lifecycle import PluginStatus, PluginStatusResult, PortStatus
from atk.plugin_schema import PluginMaturity

_MATURITY_DISPLAY: dict[PluginMaturity, str] = {
    PluginMaturity.AI_GENERATED: "[red]ai-generated[/red]",
    PluginMaturity.COMMUNITY: "[yellow]community[/yellow]",
    PluginMaturity.VERIFIED: "[green]verified[/green]",
}

console = Console()


def _format_port(port_status: PortStatus) -> str:
    """Format a port with listening status indicator."""
    if not isinstance(port_status, PortStatus):
        return str(port_status)

    if port_status.listening is None:
        return str(port_status.port)
    elif port_status.listening:
        return f"[green]{port_status.port} ✓[/green]"
    else:
        return f"[red]{port_status.port} ✗[/red]"


def _format_env_status(
    missing_required_vars: list[str], unset_optional_count: int, total_env_vars: int
) -> str:
    """Format environment variable status for display.

    Returns:
        - "-" if no env vars defined
        - "[green]✓[/green]" if all required vars are set
        - "[red]! VAR1, VAR2[/red] [dim](+N optional)[/dim]" if required vars missing
    """
    if total_env_vars == 0:
        return "-"

    if not missing_required_vars:
        return "[green]✓[/green]"

    var_list = ", ".join(missing_required_vars)
    result = f"[red]! {var_list}[/red]"

    if unset_optional_count > 0:
        result += f" [dim](+{unset_optional_count} optional)[/dim]"

    return result


def print_status_table(results: list[PluginStatusResult]) -> None:
    """Print a status table for the given plugin status results."""
    table = Table(show_header=True, header_style="bold")
    table.add_column("NAME", style="cyan")
    table.add_column("STATUS")
    table.add_column("PORTS")
    table.add_column("ENV")
    table.add_column("MATURITY")

    for result in results:
        if not isinstance(result, PluginStatusResult):
            continue

        if result.status == PluginStatus.RUNNING:
            status_str = "[green]running[/green]"
        elif result.status == PluginStatus.STOPPED:
            status_str = "[red]stopped[/red]"
        elif result.status == PluginStatus.MCP_ONLY:
            status_str = "[blue]mcp-only[/blue]"
        else:
            status_str = "[yellow]unknown[/yellow]"

        ports_str = ", ".join(_format_port(p) for p in result.ports) if result.ports else "-"

        env_str = _format_env_status(
            result.missing_required_vars, result.unset_optional_count, result.total_env_vars
        )

        maturity_str = _MATURITY_DISPLAY.get(result.maturity, str(result.maturity))

        name = f"{result.name} ({result.directory})"
        table.add_row(name, status_str, ports_str, env_str, maturity_str)

    console.print(table)

    has_port_checks = any(p.listening is not None for r in results for p in r.ports)
    has_env_vars = any(r.total_env_vars > 0 for r in results)
    has_unverified = any(r.maturity != PluginMaturity.VERIFIED for r in results)

    if has_port_checks or has_env_vars or has_unverified:
        console.print()
        console.print("[dim]Legend:[/dim]")

        if has_port_checks:
            console.print(
                "[dim]  Ports: [/dim][green]✓[/green][dim] listening, [/dim]"
                "[red]✗[/red][dim] not listening[/dim]"
            )

        if has_env_vars:
            console.print(
                "[dim]  ENV: [/dim][green]✓[/green][dim] all required vars set, "
                "[/dim][red]![/red][dim] missing required vars, [/dim]-[dim] no env vars defined[/dim]"
            )

        if has_unverified:
            console.print(
                "[dim]  Maturity: [/dim][green]verified[/green][dim] = official registry, "
                "[/dim][yellow]community[/yellow][dim] = unverified third-party, "
                "[/dim][red]ai-generated[/red][dim] = AI output, no human review[/dim]"
            )

        if has_port_checks:
            console.print()
            console.print(
                "[dim]Note: Port checks verify if something is listening, not that it's the plugin.[/dim]"
            )


def print_repo_status(atk_home: Path) -> None:
    """Print git repository status section after the plugin table."""
    console.print()
    console.print("[bold]Repository:[/bold]")

    # Branch
    branch = git_get_branch(atk_home)
    branch_str = branch if branch else "(detached)"
    console.print(f"  Branch:      {branch_str}")

    # Remote
    remote_info = git_get_remote_url(atk_home)
    if remote_info:
        remote_name, remote_url = remote_info
        console.print(f"  Remote:      {remote_name} -> {remote_url}")
    else:
        console.print("  Remote:      [dim](none)[/dim]")

    # Sync (only if remote exists)
    if remote_info:
        ab = git_ahead_behind(atk_home)
        if ab:
            console.print(f"  Sync:        {ab.ahead} ahead, {ab.behind} behind")
        else:
            console.print("  Sync:        [dim](no tracking branch)[/dim]")

    # Last commit
    commit = git_last_commit_info(atk_home)
    if commit:
        console.print(f"  Last commit: {commit.subject} ({commit.relative_time})")

    # Working directory
    wd = git_working_dir_status(atk_home)
    if wd.is_clean:
        console.print("  Working dir: [green]clean[/green]")
    else:
        parts = []
        if wd.modified:
            parts.append(f"{wd.modified} modified")
        if wd.untracked:
            parts.append(f"{wd.untracked} untracked")
        console.print(f"  Working dir: [yellow]{', '.join(parts)}[/yellow]")

