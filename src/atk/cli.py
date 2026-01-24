"""ATK CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from atk import exit_codes
from atk.add import add_plugin
from atk.banner import print_banner
from atk.git import is_git_available
from atk.home import get_atk_home, validate_atk_home
from atk.init import init_atk_home
from atk.lifecycle import (
    LifecycleCommand,
    LifecycleCommandNotDefinedError,
    PluginStatus,
    PluginStatusResult,
    PortStatus,
    get_all_plugins_status,
    get_plugin_status,
    restart_all_plugins,
    run_all_plugins_lifecycle,
    run_plugin_lifecycle,
)
from atk.manifest_schema import load_manifest
from atk.plugin import PluginNotFoundError
from atk.remove import remove_plugin

app = typer.Typer(
    name="atk",
    help="Agent Toolkit - Manage AI development tools through a git-backed, declarative manifest.",
    no_args_is_help=True,
)

console = Console()


def require_initialized_home() -> Path:
    """Get ATK Home and verify it is initialized.

    Returns:
        Path to the initialized ATK Home directory.

    Raises:
        typer.Exit: With HOME_NOT_INITIALIZED if ATK Home is not initialized.
    """
    atk_home = get_atk_home()
    validation = validate_atk_home(atk_home)

    if not validation.is_valid:
        console.print(f"[red]✗[/red] ATK Home not initialized at {atk_home}")
        console.print("  Run [bold]atk init[/bold] first.")
        raise typer.Exit(exit_codes.HOME_NOT_INITIALIZED)

    return atk_home


def require_git() -> None:
    """Verify git is available on the system.

    Raises:
        typer.Exit: With GIT_ERROR if git is not available.
    """
    if not is_git_available():
        console.print("[red]✗[/red] Git is not available")
        console.print("  [dim]•[/dim] ATK requires git for repository management")
        raise typer.Exit(exit_codes.GIT_ERROR)


def require_ready_home() -> Path:
    """Get ATK Home, verify initialized, and check git if auto_commit enabled.

    This is the standard precondition check for most ATK commands.
    Combines require_initialized_home() with git availability check
    when auto_commit is enabled in the manifest.

    Returns:
        Path to the initialized ATK Home directory.

    Raises:
        typer.Exit: With HOME_NOT_INITIALIZED if not initialized.
        typer.Exit: With GIT_ERROR if auto_commit enabled but git unavailable.
    """
    atk_home = require_initialized_home()

    # Check if git is needed (auto_commit enabled)
    manifest = load_manifest(atk_home)
    if manifest.config.auto_commit:
        require_git()

    return atk_home


def _run_lifecycle_cli(
    command_name: LifecycleCommand,
    plugin: str | None,
    all_plugins: bool,
    *,
    reverse: bool = False,
) -> None:
    """Run a lifecycle command from CLI with proper output and exit codes.

    Args:
        command_name: The lifecycle command to run (install, start, stop, etc.)
        plugin: Plugin identifier (name or directory) or None for --all
        all_plugins: Whether to run on all plugins
        reverse: If True, process plugins in reverse order (for stop)
    """
    atk_home = require_ready_home()

    # Past tense for success messages
    past_tense = {
        "install": "Installed",
        "start": "Started",
        "stop": "Stopped",
        "restart": "Restarted",
    }
    verb = past_tense.get(command_name, command_name.capitalize() + "ed")

    # Validate arguments
    if all_plugins and plugin:
        console.print("[red]✗[/red] Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        console.print("[red]✗[/red] Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if all_plugins:
        result = run_all_plugins_lifecycle(atk_home, command_name, reverse=reverse)
        for name in result.succeeded:
            console.print(f"[green]✓[/green] {verb} plugin '{name}'")
        for name in result.skipped:
            console.print(
                f"[yellow]![/yellow] Plugin '{name}' has no {command_name} command defined"
            )
        for name, code in result.failed:
            console.print(
                f"[red]✗[/red] {command_name.capitalize()} failed for plugin '{name}' (exit code {code})"
            )

        if result.all_succeeded:
            raise typer.Exit(exit_codes.SUCCESS)
        else:
            raise typer.Exit(exit_codes.GENERAL_ERROR)

    # Single plugin
    try:
        exit_code = run_plugin_lifecycle(atk_home, plugin, command_name)  # type: ignore[arg-type]
        if exit_code == 0:
            console.print(f"[green]✓[/green] {verb} plugin '{plugin}'")
        else:
            console.print(
                f"[red]✗[/red] {command_name.capitalize()} failed for plugin '{plugin}' (exit code {exit_code})"
            )
        raise typer.Exit(exit_code)
    except PluginNotFoundError:
        console.print(f"[red]✗[/red] Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None
    except LifecycleCommandNotDefinedError:
        console.print(
            f"[yellow]![/yellow] Plugin '{plugin}' has no {command_name} command defined"
        )
        raise typer.Exit(exit_codes.SUCCESS) from None


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        print_banner()
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        callback=version_callback,
        is_eager=True,
        help="Show ATK version and exit.",
    ),
) -> None:
    """Agent Toolkit - Manage AI development tools through a git-backed, declarative manifest."""


@app.command()
def init(
    directory: Annotated[
        Path | None,
        typer.Argument(
            help="Target directory to initialize. Defaults to ATK_HOME or ~/.atk/",
        ),
    ] = None,
) -> None:
    """Initialize ATK Home directory.

    Creates the directory structure, initializes git repository, and creates
    initial commit. If already initialized, this is a no-op.
    """
    # Verify git is available before creating any directories
    require_git()

    # Resolve target directory
    target = directory if directory else get_atk_home()

    result = init_atk_home(target)

    if result.is_valid:
        console.print(f"[green]✓[/green] ATK Home initialized at {target}")
        raise typer.Exit(exit_codes.SUCCESS)
    else:
        console.print(f"[red]✗[/red] Failed to initialize ATK Home at {target}")
        for error in result.errors:
            console.print(f"  [dim]•[/dim] {error}")
        raise typer.Exit(exit_codes.GENERAL_ERROR)


@app.command()
def add(
    source: Annotated[
        Path,
        typer.Argument(
            help="Path to plugin directory or single plugin.yaml file.",
        ),
    ],
) -> None:
    """Add a plugin to ATK Home.

    Copies plugin files to ATK Home and updates the manifest.
    If the plugin directory already exists, it will be overwritten.
    """
    atk_home = require_ready_home()

    # Validate source exists
    if not source.exists():
        console.print(f"[red]✗[/red] Source path does not exist: {source}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID)

    try:
        directory = add_plugin(source, atk_home)
        console.print(f"[green]✓[/green] Added plugin to {atk_home}/plugins/{directory}")
        raise typer.Exit(exit_codes.SUCCESS)
    except ValueError as e:
        console.print(f"[red]✗[/red] Failed to add plugin: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e


@app.command()
def remove(
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory to remove.",
        ),
    ],
) -> None:
    """Remove a plugin from ATK Home.

    Removes the plugin directory and updates the manifest.
    Accepts either the plugin name or directory name.
    If the plugin is not found, this is a no-op.
    """
    atk_home = require_ready_home()

    try:
        removed = remove_plugin(plugin, atk_home)
        if removed:
            console.print(f"[green]✓[/green] Removed plugin '{plugin}'")
        else:
            console.print(f"[yellow]![/yellow] Plugin '{plugin}' not found (no-op)")
        raise typer.Exit(exit_codes.SUCCESS)
    except ValueError as e:
        console.print(f"[red]✗[/red] Failed to remove plugin: {e}")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from e


@app.command()
def install(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to install.",
        ),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Install all plugins in manifest order.",
        ),
    ] = False,
) -> None:
    """Run the install lifecycle command for a plugin.

    Executes the install command defined in the plugin's plugin.yaml.
    Shows a warning if no install command is defined.
    """
    _run_lifecycle_cli("install", plugin, all_plugins)


@app.command()
def start(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to start.",
        ),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Start all plugins in manifest order.",
        ),
    ] = False,
) -> None:
    """Run the start lifecycle command for a plugin.

    Executes the start command defined in the plugin's plugin.yaml.
    Shows a warning if no start command is defined.
    """
    _run_lifecycle_cli("start", plugin, all_plugins)


@app.command()
def stop(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to stop.",
        ),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Stop all plugins in reverse manifest order.",
        ),
    ] = False,
) -> None:
    """Run the stop lifecycle command for a plugin.

    Executes the stop command defined in the plugin's plugin.yaml.
    Shows a warning if no stop command is defined.

    When using --all, plugins are stopped in REVERSE manifest order
    (opposite of start order) to handle dependencies correctly.
    """
    _run_lifecycle_cli("stop", plugin, all_plugins, reverse=True)


@app.command()
def restart(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to restart.",
        ),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Restart all plugins (stop all, then start all).",
        ),
    ] = False,
) -> None:
    """Run the restart lifecycle command for a plugin.

    For a single plugin: Executes the restart command defined in plugin.yaml.
    Shows a warning if no restart command is defined.

    For --all: Stops all plugins in reverse order, then starts all in
    manifest order. If the stop phase has failures, the start phase is skipped.
    """
    # Single plugin case - use standard lifecycle handler
    if plugin and not all_plugins:
        _run_lifecycle_cli("restart", plugin, all_plugins)
        return

    # --all case - custom two-phase handling
    if all_plugins and plugin:
        console.print("[red]✗[/red] Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        console.print("[red]✗[/red] Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    atk_home = require_ready_home()
    result = restart_all_plugins(atk_home)

    # Report stop phase results
    for name in result.stop_succeeded:
        console.print(f"[green]✓[/green] Stopped plugin '{name}'")
    for name in result.stop_skipped:
        console.print(f"[yellow]![/yellow] Plugin '{name}' has no stop command defined")
    for name, code in result.stop_failed:
        console.print(f"[red]✗[/red] Stop failed for plugin '{name}' (exit code {code})")

    # If stop phase failed, report and exit
    if not result.stop_result.all_succeeded:
        console.print("[red]✗[/red] Restart aborted: stop phase had failures")
        raise typer.Exit(exit_codes.GENERAL_ERROR)

    # Report start phase results
    for name in result.start_succeeded:
        console.print(f"[green]✓[/green] Started plugin '{name}'")
    for name in result.start_skipped:
        console.print(f"[yellow]![/yellow] Plugin '{name}' has no start command defined")
    for name, code in result.start_failed:
        console.print(f"[red]✗[/red] Start failed for plugin '{name}' (exit code {code})")

    if result.all_succeeded:
        raise typer.Exit(exit_codes.SUCCESS)
    else:
        raise typer.Exit(exit_codes.GENERAL_ERROR)


@app.command()
def status(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to check status for.",
        ),
    ] = None,
) -> None:
    """Show status of installed plugins.

    If a plugin is specified, shows status for that plugin only.
    Otherwise, shows status for all plugins in a table format.
    """
    atk_home = require_initialized_home()

    # Single plugin status
    if plugin:
        try:
            result = get_plugin_status(atk_home, plugin)
            _print_status_table([result])
            raise typer.Exit(exit_codes.SUCCESS)
        except PluginNotFoundError:
            console.print(f"[red]✗[/red] Plugin '{plugin}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

    # All plugins status
    results = get_all_plugins_status(atk_home)

    if not results:
        console.print("[dim]No plugins installed.[/dim]")
        raise typer.Exit(exit_codes.SUCCESS)

    _print_status_table(results)
    raise typer.Exit(exit_codes.SUCCESS)


@app.command()
def logs(
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory to view logs for.",
        ),
    ],
) -> None:
    """View logs for a plugin.

    Runs the logs lifecycle command defined in the plugin's plugin.yaml.
    Shows a warning if no logs command is defined.
    """
    atk_home = require_initialized_home()

    try:
        exit_code = run_plugin_lifecycle(atk_home, plugin, "logs")
        raise typer.Exit(exit_code)
    except PluginNotFoundError:
        console.print(f"[red]✗[/red] Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None
    except LifecycleCommandNotDefinedError:
        console.print(
            f"[yellow]![/yellow] Plugin '{plugin}' has no logs command defined"
        )
        raise typer.Exit(exit_codes.SUCCESS) from None


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


def _print_status_table(results: list[PluginStatusResult]) -> None:
    """Print a status table for the given plugin status results."""

    table = Table(show_header=True, header_style="bold")
    table.add_column("NAME", style="cyan")
    table.add_column("STATUS")
    table.add_column("PORTS")

    for result in results:
        if not isinstance(result, PluginStatusResult):
            continue

        if result.status == PluginStatus.RUNNING:
            status_str = "[green]running[/green]"
        elif result.status == PluginStatus.STOPPED:
            status_str = "[red]stopped[/red]"
        else:
            status_str = "[yellow]unknown[/yellow]"

        ports_str = ", ".join(_format_port(p) for p in result.ports) if result.ports else "-"

        table.add_row(result.name, status_str, ports_str)

    console.print(table)

    has_port_checks = any(
        p.listening is not None for r in results for p in r.ports
    )
    if has_port_checks:
        console.print()
        console.print("[dim]Legend: ✓ port listening, ✗ port not listening[/dim]")
        console.print("[dim]Note: Port checks verify if something is listening, not that it's the plugin.[/dim]")


if __name__ == "__main__":
    app()

