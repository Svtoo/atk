"""ATK CLI entry point."""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markdown import Markdown

from atk import __version__, cli_logger, exit_codes
from atk.add import AddCancelledError, InstallFailedError, add_plugin
from atk.banner import print_banner
from atk.commands.lifecycle import run_lifecycle_cli, run_restart_single_cli, run_uninstall_cli
from atk.commands.preconditions import (
    assert_plugin_or_all,
    require_git,
    require_initialized_home,
    require_plugin,
    require_ready_home,
    stdin_prompt,
)
from atk.commands.plug import plug_plugin, unplug_plugin
from atk.commands.run import run_plugin_script
from atk.commands.search import filter_registry_plugins, print_search_table
from atk.commands.status import print_status_table
from atk.commands.upgrade import upgrade_all_plugins, upgrade_single_plugin
from atk.errors import handle_cli_error
from atk.git_source import GitPluginNotFoundError, GitSourceError
from atk.home import get_atk_home
from atk.init import init_atk_home
from atk.lifecycle import (
    LifecycleCommandNotDefinedError,
    get_all_plugins_status,
    get_plugin_status,
    restart_all_plugins,
    run_plugin_lifecycle,
)
from atk.manifest_schema import load_manifest
from atk.mcp import format_mcp_plaintext, generate_mcp_config
from atk.plugin import PluginNotFoundError, load_plugin
from atk.registry import (
    PluginNotFoundError as RegistryPluginNotFoundError,
)
from atk.registry import (
    RegistryFetchError,
    fetch_registry_index,
)
from atk.remove import remove_plugin
from atk.setup import run_setup
from atk.update_check import get_update_notice

app = typer.Typer(
    name="atk",
    help="AI Toolkit - Manage AI development tools through a git-backed, declarative manifest.",
    no_args_is_help=True,
)

console = Console()




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
    """AI Toolkit - Manage AI development tools through a git-backed, declarative manifest."""


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
        cli_logger.success(f"ATK Home initialized at {target}")
        raise typer.Exit(exit_codes.SUCCESS)
    else:
        cli_logger.error(f"Failed to initialize ATK Home at {target}")
        for error in result.errors:
            cli_logger.dim(f"  • {error}")
        raise typer.Exit(exit_codes.GENERAL_ERROR)


@app.command()
def search(
    query: Annotated[
        str | None,
        typer.Argument(
            help="Filter plugins by name or description (case-insensitive). Lists all if omitted.",
        ),
    ] = None,
) -> None:
    """Search available plugins in the ATK registry.

    With no arguments, lists all available plugins.
    Provide a search term to filter by name or description.
    """
    atk_home = require_initialized_home()
    manifest = load_manifest(atk_home)
    installed = {p.directory for p in manifest.plugins}

    try:
        index = fetch_registry_index()
    except RegistryFetchError as e:
        cli_logger.error(f"Failed to fetch registry: {e}")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from e

    plugins = index.plugins
    if query:
        plugins = filter_registry_plugins(plugins, query)

    print_search_table(plugins, installed, query)
    raise typer.Exit(exit_codes.SUCCESS)


@app.command()
def add(
    source: Annotated[
        str,
        typer.Argument(
            help="Plugin source: local path, registry name, or git URL.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "-y",
            "--force",
            help="Skip the maturity confirmation prompt for unverified plugins.",
        ),
    ] = False,
) -> None:
    """Add a plugin to ATK Home.

    Accepts a local path, registry plugin name, or git URL.
    If the plugin has environment variables, prompts for configuration before install.
    Warns and asks for confirmation when the plugin maturity is below 'verified'
    (use -y / --force to skip the prompt).
    """
    atk_home = require_ready_home()

    confirm_func = (lambda _: True) if force else (lambda msg: typer.confirm(msg, default=False))

    try:
        directory = add_plugin(source, atk_home, stdin_prompt, confirm_func=confirm_func)
        cli_logger.success(f"Added plugin to {atk_home}/plugins/{directory}")
        raise typer.Exit(exit_codes.SUCCESS)
    except AddCancelledError:
        cli_logger.info("Installation cancelled")
        raise typer.Exit(exit_codes.SUCCESS) from None
    except RegistryPluginNotFoundError as e:
        cli_logger.error(f"Plugin not found in registry: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e
    except InstallFailedError as e:
        cli_logger.error(f"Install failed for plugin '{e.plugin_name}' (exit code {e.exit_code})")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from e
    except (ValueError, FileNotFoundError) as e:
        cli_logger.error(f"Failed to add plugin: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e
    except GitPluginNotFoundError as e:
        cli_logger.error(f"Git repo does not contain an ATK plugin: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e
    except GitSourceError as e:
        cli_logger.error(f"Failed to fetch from git: {e}")
        raise typer.Exit(exit_codes.GIT_ERROR) from e


@app.command()
def remove(
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory to remove.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Skip confirmation prompt and continue past lifecycle failures.",
        ),
    ] = False,
) -> None:
    """Remove a plugin from ATK Home.

    Removes the plugin directory and updates the manifest.
    Runs stop and uninstall lifecycle commands before removal (if defined).
    Accepts either the plugin name or directory name.
    If the plugin is not found, this is a no-op.
    Prompts for confirmation when uninstall lifecycle is defined (use --force to skip).
    """
    atk_home = require_ready_home()

    # Check if plugin has uninstall lifecycle and prompt for confirmation
    if not force:
        try:
            plugin_schema, _ = load_plugin(atk_home, plugin)
            if (
                plugin_schema.lifecycle is not None
                and plugin_schema.lifecycle.uninstall is not None
            ):
                console.print(
                    f"\n⚠️  This will run the uninstall command which may delete data:\n"
                    f"    {plugin_schema.lifecycle.uninstall}\n",
                    style="yellow",
                )
                confirm = typer.confirm("Continue?", default=False)
                if not confirm:
                    cli_logger.info("Remove cancelled")
                    raise typer.Exit(exit_codes.SUCCESS)
        except PluginNotFoundError:
            # Plugin not in manifest — remove_plugin will handle (no-op or orphan cleanup)
            pass

    try:
        result = remove_plugin(plugin, atk_home, force=force)
        if result.removed:
            if result.orphan_cleaned:
                cli_logger.warning(
                    f"Plugin '{plugin}' was not in the manifest, but an orphaned directory "
                    f"was found at ~/.atk/plugins/{plugin}/ and removed. "
                    f"A previous install likely failed partway through."
                )
            else:
                if result.stop_failed:
                    cli_logger.warning(
                        f"Warning: stop failed for '{plugin}' (exit code {result.stop_exit_code})"
                    )
                if result.uninstall_failed:
                    cli_logger.warning(
                        f"Warning: uninstall failed for '{plugin}' (exit code {result.uninstall_exit_code})"
                    )
                cli_logger.success(f"Removed plugin '{plugin}'")
        elif result.uninstall_failed:
            cli_logger.error(
                f"Uninstall failed for '{plugin}' (exit code {result.uninstall_exit_code}). "
                f"Plugin was NOT removed. Fix the issue and retry, "
                f"or use --force to remove anyway."
            )
            raise typer.Exit(exit_codes.GENERAL_ERROR)
        else:
            cli_logger.warning(f"Plugin '{plugin}' not found (no-op)")
        raise typer.Exit(exit_codes.SUCCESS)
    except ValueError as e:
        cli_logger.error(f"Failed to remove plugin: {e}")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from e



@app.command()
def upgrade(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to upgrade.",
        ),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Upgrade all upgradeable plugins (skips local plugins).",
        ),
    ] = False,
) -> None:
    """Upgrade a plugin to the latest remote version.

    Checks the remote for a newer commit, fetches if needed, preserves
    the custom/ directory, and detects new required environment variables.

    Local plugins cannot be upgraded and are skipped with --all.
    """
    assert_plugin_or_all(plugin, all_plugins)
    atk_home = require_ready_home()

    if plugin:
        upgrade_single_plugin(atk_home, plugin)
    else:
        upgrade_all_plugins(atk_home)


@app.command()
def setup(
    plugin: Annotated[
        str | None,
        typer.Argument(
            help="Plugin name or directory to configure.",
        ),
    ] = None,
    all_plugins: Annotated[
        bool,
        typer.Option(
            "--all",
            help="Configure all plugins with environment variables.",
        ),
    ] = False,
) -> None:
    """Configure environment variables for a plugin.

    Prompts for each environment variable defined in the plugin's plugin.yaml.
    Saves values to the plugin's .env file.
    """
    atk_home = require_ready_home()

    assert_plugin_or_all(plugin, all_plugins)

    if plugin:
        plugin_schema, plugin_dir = require_plugin(atk_home, plugin)

        if not plugin_schema.env_vars:
            cli_logger.info(f"Plugin '{plugin_schema.name}' has no environment variables defined")
            raise typer.Exit(exit_codes.SUCCESS)

        result = run_setup(plugin_schema, plugin_dir, stdin_prompt)
        cli_logger.success(f"Configured {len(result.configured_vars)} variable(s) for '{result.plugin_name}'")
        raise typer.Exit(exit_codes.SUCCESS)

    manifest = load_manifest(atk_home)
    for plugin_entry in manifest.plugins:
        plugin_schema, plugin_dir = load_plugin(atk_home, plugin_entry.directory)
        if not plugin_schema.env_vars:
            continue
        cli_logger.info(f"\nConfiguring '{plugin_schema.name}':")
        result = run_setup(plugin_schema, plugin_dir, stdin_prompt)
        cli_logger.success(f"Configured {len(result.configured_vars)} variable(s)")

    raise typer.Exit(exit_codes.SUCCESS)


@app.command()
def mcp(
    plugin: Annotated[
        str,
        typer.Argument(help="Plugin name or directory."),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON instead of plaintext."),
    ] = False,
) -> None:
    """Display the MCP configuration for a plugin.

    Reads the MCP section from plugin.yaml, resolves environment variables
    from the plugin's .env file, and prints the result.  The output can be
    copied directly into an IDE or tool configuration file.

    Use --json to get machine-readable JSON output.

    To wire plugins into coding agents, use 'atk plug' / 'atk unplug'.
    """
    atk_home = require_ready_home()

    plugin_schema, plugin_dir = require_plugin(atk_home, plugin)

    if plugin_schema.mcp is None:
        cli_logger.error(f"Plugin '{plugin_schema.name}' has no MCP configuration")
        raise typer.Exit(exit_codes.PLUGIN_INVALID)

    result = generate_mcp_config(plugin_schema, plugin_dir, plugin_schema.name)

    for var in result.missing_vars:
        cli_logger.warning(f"Environment variable '{var}' is not set")

    if json_output:
        print(json.dumps(result.to_mcp_dict(), indent=2))
    else:
        console.print(format_mcp_plaintext(result))

    raise typer.Exit(exit_codes.SUCCESS)


# ---------------------------------------------------------------------------
# atk plug / atk unplug
# ---------------------------------------------------------------------------


@app.command()
def plug(
    plugin: Annotated[
        str,
        typer.Argument(help="Plugin name or directory."),
    ],
    claude: Annotated[
        bool,
        typer.Option("--claude", help="Plug into Claude Code."),
    ] = False,
    codex: Annotated[
        bool,
        typer.Option("--codex", help="Plug into Codex."),
    ] = False,
    gemini: Annotated[
        bool,
        typer.Option("--gemini", help="Plug into Gemini CLI."),
    ] = False,
    auggie: Annotated[
        bool,
        typer.Option("--auggie", help="Plug into Augment Code."),
    ] = False,
    opencode: Annotated[
        bool,
        typer.Option("--opencode", help="Plug into OpenCode."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("-y", "--force", help="Skip all confirmation prompts."),
    ] = False,
) -> None:
    """Plug a plugin into one or more coding agents.

    Adapts to what the plugin offers: registers the MCP server, injects
    the SKILL.md, or both.  Plugins with only a SKILL.md (no MCP server)
    are supported — enabling instruction-only plugins like coding personas.

    Pass -y / --force to skip all confirmation prompts.

    Multiple agent flags may be combined; agents are processed in order:
    Claude → Codex → Gemini → Auggie → OpenCode.
    """
    agent_flags = [claude, codex, gemini, auggie, opencode]

    if not any(agent_flags):
        cli_logger.warning(
            "No agent flags specified — pass one or more of "
            "--claude, --codex, --gemini, --auggie, --opencode"
        )
        raise typer.Exit(exit_codes.SUCCESS)

    atk_home = require_ready_home()
    plugin_schema, plugin_dir = require_plugin(atk_home, plugin)

    code = plug_plugin(
        plugin_schema, plugin_dir,
        claude=claude, codex=codex, gemini=gemini,
        auggie=auggie, opencode=opencode, force=force,
    )
    raise typer.Exit(code)


@app.command()
def unplug(
    plugin: Annotated[
        str,
        typer.Argument(help="Plugin name or directory."),
    ],
    claude: Annotated[
        bool,
        typer.Option("--claude", help="Unplug from Claude Code."),
    ] = False,
    codex: Annotated[
        bool,
        typer.Option("--codex", help="Unplug from Codex."),
    ] = False,
    gemini: Annotated[
        bool,
        typer.Option("--gemini", help="Unplug from Gemini CLI."),
    ] = False,
    auggie: Annotated[
        bool,
        typer.Option("--auggie", help="Unplug from Augment Code."),
    ] = False,
    opencode: Annotated[
        bool,
        typer.Option("--opencode", help="Unplug from OpenCode."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("-y", "--force", help="Skip all confirmation prompts."),
    ] = False,
) -> None:
    """Unplug a plugin from one or more coding agents.

    Removes MCP server registration, SKILL.md references, or both —
    depending on what the plugin offers.

    Pass -y / --force to skip all confirmation prompts.

    Multiple agent flags may be combined; agents are processed in order:
    Claude → Codex → Gemini → Auggie → OpenCode.
    """
    agent_flags = [claude, codex, gemini, auggie, opencode]

    if not any(agent_flags):
        cli_logger.warning(
            "No agent flags specified — pass one or more of "
            "--claude, --codex, --gemini, --auggie, --opencode"
        )
        raise typer.Exit(exit_codes.SUCCESS)

    atk_home = require_ready_home()
    plugin_schema, plugin_dir = require_plugin(atk_home, plugin)

    code = unplug_plugin(
        plugin_schema, plugin_dir,
        claude=claude, codex=codex, gemini=gemini,
        auggie=auggie, opencode=opencode, force=force,
    )
    raise typer.Exit(code)


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
    run_lifecycle_cli("install", plugin, all_plugins)


@app.command()
def uninstall(
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory to uninstall.",
        ),
    ],
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="Skip confirmation prompt.",
        ),
    ] = False,
) -> None:
    """Run the uninstall lifecycle command for a plugin.

    Runs stop and uninstall lifecycle commands to clean up resources.
    Does NOT remove the plugin from manifest (use 'atk remove' for that).
    Symmetric to 'atk install': install sets up, uninstall tears down.
    """
    atk_home = require_ready_home()
    plugin_schema, plugin_dir = require_plugin(atk_home, plugin)
    run_uninstall_cli(plugin_schema, plugin_dir, force=force)


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
    run_lifecycle_cli("start", plugin, all_plugins)


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
    run_lifecycle_cli("stop", plugin, all_plugins, reverse=True)


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
    """Restart a plugin by executing stop then start.

    For a single plugin: Executes stop then start in sequence.
    If stop fails, start is not attempted.

    For --all: Stops all plugins in reverse order, then starts all in
    manifest order. If the stop phase has failures, the start phase is skipped.
    """
    # Single plugin case - delegate stop-then-start to commands layer
    if plugin and not all_plugins:
        atk_home = require_ready_home()
        run_restart_single_cli(atk_home, plugin)
        return

    # --all case - custom two-phase handling
    assert_plugin_or_all(plugin, all_plugins)
    atk_home = require_ready_home()
    result = restart_all_plugins(atk_home)

    # Report stop phase results
    for name in result.stop_succeeded:
        cli_logger.success(f"Stopped plugin '{name}'")
    for name in result.stop_skipped:
        cli_logger.warning(f"Plugin '{name}' has no stop command defined")
    for name, code in result.stop_failed:
        cli_logger.error(f"Stop failed for plugin '{name}' (exit code {code})")

    # If stop phase failed, report and exit
    if not result.stop_result.all_succeeded:
        cli_logger.error("Restart aborted: stop phase had failures")
        raise typer.Exit(exit_codes.GENERAL_ERROR)

    # Report start phase results
    for name in result.start_succeeded:
        cli_logger.success(f"Started plugin '{name}'")
    for name in result.start_skipped:
        cli_logger.warning(f"Plugin '{name}' has no start command defined")
    for name, code in result.start_failed:
        cli_logger.error(f"Start failed for plugin '{name}' (exit code {code})")

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
            print_status_table([result])
            raise typer.Exit(exit_codes.SUCCESS)
        except PluginNotFoundError:
            cli_logger.error(f"Plugin '{plugin}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

    # All plugins status
    results = get_all_plugins_status(atk_home)

    if not results:
        cli_logger.dim("No plugins installed.")
        raise typer.Exit(exit_codes.SUCCESS)

    print_status_table(results)
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
        cli_logger.error(f"Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None
    except LifecycleCommandNotDefinedError:
        cli_logger.warning(f"Plugin '{plugin}' has no logs command defined")
        raise typer.Exit(exit_codes.SUCCESS) from None



@app.command(name="help")
def plugin_help(
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory to show documentation for.",
        ),
    ],
) -> None:
    """Show plugin documentation (README.md).

    Renders the plugin's README.md as formatted Markdown in the terminal.
    """
    atk_home = require_initialized_home()

    _, plugin_dir = require_plugin(atk_home, plugin)

    readme_path = plugin_dir / "README.md"
    if not readme_path.exists():
        cli_logger.warning(f"Plugin '{plugin}' has no README.md")
        raise typer.Exit(exit_codes.SUCCESS)

    console.print(Markdown(readme_path.read_text()))
    raise typer.Exit(exit_codes.SUCCESS)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    ctx: typer.Context,
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory.",
        ),
    ],
    script: Annotated[
        str,
        typer.Argument(
            help="Script name to run (with or without .sh extension).",
        ),
    ],
) -> None:
    """Run a script from a plugin directory.

    Looks for the script in the plugin's root directory.
    If the script name doesn't have an extension, tries adding .sh.
    Any additional arguments after the script name are forwarded to the script.
    """
    atk_home = require_initialized_home()

    _, plugin_dir = require_plugin(atk_home, plugin)

    run_plugin_script(plugin_dir, script, ctx.args)


def _show_update_notice() -> None:
    """Show update notice if a newer version is available on PyPI.

    Suppressed when stderr is not a TTY (piped output).
    Errors are silently ignored — update check must never crash the CLI.
    """
    if not sys.stderr.isatty():
        return
    try:
        notice = get_update_notice(__version__, get_atk_home())
    except (OSError, ValueError, KeyError):
        return
    if notice is not None:
        cli_logger.warning(notice)


def main_cli() -> None:
    """CLI entry point with top-level exception handling.

    Wraps the Typer app to catch any unhandled exceptions and format them
    as clean error messages instead of raw tracebacks.
    """
    try:
        app()
    except Exception as e:
        sys.exit(handle_cli_error(e))
    finally:
        _show_update_notice()


if __name__ == "__main__":
    main_cli()

