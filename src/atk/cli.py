"""ATK CLI entry point."""

import typer
from rich.console import Console

from atk import __version__

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
def status() -> None:
    """Show status of all installed plugins."""
    typer.echo("No plugins installed yet.")


if __name__ == "__main__":
    app()

