"""ATK CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from atk import __version__, exit_codes
from atk.add import add_plugin
from atk.git import is_git_available
from atk.home import get_atk_home, validate_atk_home
from atk.init import init_atk_home
from atk.install import install_all_plugins, install_plugin
from atk.lifecycle import LifecycleCommandNotDefinedError
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


def print_banner() -> None:
    """Print the ATK ASCII art banner."""
    from rich.text import Text

    # Colors matching the ATK logo
    orange = "#F5A044"  # Inner triangles - warm orange
    charcoal = "#3D4049"  # Outer frame - dark charcoal

    # Simple ASCII art logo matching the ATK logo:
    # - Outer A-frame (charcoal)
    # - Inner orange triangle at top peak
    # - Horizontal crossbar
    # - Two orange wing triangles at bottom
    logo_art = [
        "            /\\",
        "           /  \\",
        "          / /\\ \\",
        "         / /  \\ \\",
        "        / /#|# \\ \\",
        "       / /##|## \\ \\",
        "      / /###|### \\ \\",
        "     /==============\\",
        "    / /#####/\\#####\\ \\",
        "   / /## /      \\ ##\\ \\",
        "   ==      _     _   ==",
        ]


    # Lowercase "atk" text - spaced out for readability
    text_art = [
        "    __ _  | |_  | | __",
        "   / _` | | __| | |/ /",
        "  | (_| | | |_  |   < ",
        "   \\___,| \\___| |_|\\_\\",
    ]

    # Print logo: # = orange (fill), / \ _ = charcoal (frame)
    for line in logo_art:
        text = Text()
        for char in line:
            if char == "#":
                text.append(char, style=orange)
            elif char in "/\\_-=|":
                text.append(char, style=charcoal)
            else:
                text.append(char)  # spaces
        console.print(text)

    # Print "atk" text in charcoal (no extra gap)
    for line in text_art:
        text = Text()
        for char in line:
            if char == " ":
                text.append(char)
            else:
                text.append(char, style=charcoal)
        console.print(text)

    console.print()
    console.print(f"[bold white]atk[/bold white] v{__version__} - AI Toolkit for MCP Integrations")
    console.print()


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
    atk_home = require_ready_home()

    # Validate arguments
    if all_plugins and plugin:
        console.print("[red]✗[/red] Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        console.print("[red]✗[/red] Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if all_plugins:
        result = install_all_plugins(atk_home)
        for name in result.succeeded:
            console.print(f"[green]✓[/green] Installed plugin '{name}'")
        for name in result.skipped:
            console.print(f"[yellow]![/yellow] Plugin '{name}' has no install command defined")
        for name, code in result.failed:
            console.print(f"[red]✗[/red] Install failed for plugin '{name}' (exit code {code})")

        if result.all_succeeded:
            raise typer.Exit(exit_codes.SUCCESS)
        else:
            raise typer.Exit(exit_codes.GENERAL_ERROR)

    # Single plugin install
    try:
        exit_code = install_plugin(atk_home, plugin)  # type: ignore[arg-type]
        if exit_code == 0:
            console.print(f"[green]✓[/green] Installed plugin '{plugin}'")
        else:
            console.print(f"[red]✗[/red] Install failed for plugin '{plugin}' (exit code {exit_code})")
        raise typer.Exit(exit_code)
    except PluginNotFoundError:
        console.print(f"[red]✗[/red] Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND)
    except LifecycleCommandNotDefinedError:
        console.print(f"[yellow]![/yellow] Plugin '{plugin}' has no install command defined")
        raise typer.Exit(exit_codes.SUCCESS)


@app.command()
def status() -> None:
    """Show status of all installed plugins."""
    typer.echo("No plugins installed yet.")


if __name__ == "__main__":
    app()

