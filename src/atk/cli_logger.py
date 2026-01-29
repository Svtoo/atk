"""CLI output utilities for consistent messaging."""

from rich.console import Console

_console = Console()


def success(message: str) -> None:
    """Print a success message with green checkmark."""
    _console.print(f"[green]✓[/green] {message}")


def error(message: str) -> None:
    """Print an error message with red X."""
    _console.print(f"[red]✗[/red] {message}")


def warning(message: str) -> None:
    """Print a warning message with yellow exclamation."""
    _console.print(f"[yellow]![/yellow] {message}")


def info(message: str) -> None:
    """Print an info message (no prefix)."""
    _console.print(message)


def dim(message: str) -> None:
    """Print a dimmed message (for secondary info)."""
    _console.print(f"[dim]{message}[/dim]")

