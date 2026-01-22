"""ATK CLI entry point."""

import typer

from atk import __version__

app = typer.Typer(
    name="atk",
    help="Agent Toolkit - Manage AI development tools through a git-backed, declarative manifest.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    """Show version and exit."""
    if value:
        typer.echo(f"atk {__version__}")
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

