"""ATK CLI entry point."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from atk import __version__, exit_codes
from atk.add import add_plugin
from atk.home import get_atk_home, validate_atk_home
from atk.init import init_atk_home

app = typer.Typer(
    name="atk",
    help="Agent Toolkit - Manage AI development tools through a git-backed, declarative manifest.",
    no_args_is_help=True,
)

console = Console()


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
    atk_home = get_atk_home()

    # Validate ATK Home is initialized
    validation = validate_atk_home(atk_home)
    if not validation.is_valid:
        console.print(f"[red]✗[/red] ATK Home not initialized at {atk_home}")
        console.print("  Run [bold]atk init[/bold] first.")
        raise typer.Exit(exit_codes.HOME_NOT_INITIALIZED)

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
def status() -> None:
    """Show status of all installed plugins."""
    typer.echo("No plugins installed yet.")


if __name__ == "__main__":
    app()

