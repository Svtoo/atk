"""Search table rendering and filtering for the `atk search` command."""

from rich.console import Console
from rich.table import Table

from atk.registry_schema import RegistryPluginEntry

console = Console()


def filter_registry_plugins(
    plugins: list[RegistryPluginEntry],
    query: str,
) -> list[RegistryPluginEntry]:
    """Filter plugins by case-insensitive substring match on name or description.

    Args:
        plugins: Full list of registry plugin entries.
        query: Search term to match against name and description.

    Returns:
        Subset of plugins where name or description contains the query.
    """
    q = query.lower()
    return [p for p in plugins if q in p.name.lower() or q in p.description.lower()]


def print_search_table(
    plugins: list[RegistryPluginEntry],
    installed: set[str],
    query: str | None,
) -> None:
    """Render a Rich table of registry search results.

    Installed plugins are shown with a green ✓ prefix next to their name.
    Descriptions wrap naturally — no truncation.

    Args:
        plugins: Plugins to display (already filtered if a query was provided).
        installed: Set of installed plugin directory names.
        query: The search term used for filtering, or None if listing all.
    """
    if not plugins:
        if query:
            console.print(f"[dim]No plugins match '[/dim]{query}[dim]'.[/dim]")
            console.print("[dim]Run [bold]atk search[/bold] to list all available plugins.[/dim]")
        else:
            console.print("[dim]Registry is empty.[/dim]")
        return

    count = len(plugins)
    header = f"[bold]{count} plugin{'s' if count != 1 else ''}[/bold]"
    if query:
        header += f" matching '[italic]{query}[/italic]'"
    console.print(header)
    console.print()

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("NAME", no_wrap=True)
    table.add_column("DESCRIPTION")

    for entry in plugins:
        if entry.name in installed:
            name_cell = f"[green]✓ {entry.name}[/green]"
        else:
            name_cell = f"[cyan]  {entry.name}[/cyan]"
        table.add_row(name_cell, entry.description)

    console.print(table)
    console.print()
    console.print("[dim]Install with [bold]atk add <name>[/bold].[/dim]")

