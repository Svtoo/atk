"""ATK CLI entry point."""

import os
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from atk import __version__, cli_logger, exit_codes
from atk.add import InstallFailedError, add_plugin
from atk.banner import print_banner
from atk.env import load_env_file
from atk.errors import handle_cli_error
from atk.git import is_git_available
from atk.git_source import GitPluginNotFoundError, GitSourceError
from atk.home import get_atk_home, validate_atk_home
from atk.init import init_atk_home
from atk.lifecycle import (
    AllPluginsMissingEnvVars,
    AllPluginsPartialFailure,
    AllPluginsPortConflict,
    AllPluginsSuccess,
    LifecycleCommand,
    LifecycleCommandFailed,
    LifecycleCommandNotDefinedError,
    LifecycleCommandSkipped,
    LifecycleMissingEnvVars,
    LifecyclePluginNotFound,
    LifecyclePortConflict,
    LifecycleSuccess,
    PluginStatus,
    PluginStatusResult,
    PortConflict,
    PortStatus,
    execute_all_lifecycle,
    execute_lifecycle,
    get_all_plugins_status,
    get_plugin_status,
    restart_all_plugins,
    run_plugin_lifecycle,
)
from atk.manifest_schema import SourceType, load_manifest
from atk.mcp import format_mcp_plaintext, generate_mcp_config
from atk.plugin import CUSTOM_DIR, PluginNotFoundError, load_plugin
from atk.registry import PluginNotFoundError as RegistryPluginNotFoundError
from atk.remove import remove_plugin
from atk.setup import run_setup
from atk.update_check import get_update_notice
from atk.upgrade import LocalPluginError, UpgradeError, upgrade_plugin

app = typer.Typer(
    name="atk",
    help="AI Toolkit - Manage AI development tools through a git-backed, declarative manifest.",
    no_args_is_help=True,
)

console = Console()


def _stdin_prompt(text: str) -> str:
    """Prompt user for input via stdin.

    Shared helper for interactive prompts across CLI commands.
    """
    return input(text)  # For Table rendering and other rich output


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
        cli_logger.error(f"ATK Home not initialized at {atk_home}")
        cli_logger.info("  Run [bold]atk init[/bold] first.")
        raise typer.Exit(exit_codes.HOME_NOT_INITIALIZED)

    return atk_home


def require_git() -> None:
    """Verify git is available on the system.

    Raises:
        typer.Exit: With GIT_ERROR if git is not available.
    """
    if not is_git_available():
        cli_logger.error("Git is not available")
        cli_logger.dim("  • ATK requires git for repository management")
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


PAST_TENSE = {
    "install": "Installed",
    "start": "Started",
    "stop": "Stopped",
    "restart": "Restarted",
}


def _format_missing_env_vars(plugin_name: str, missing_vars: list[str]) -> None:
    """Output error message for missing required env vars."""
    cli_logger.error(f"Missing required environment variables for '{plugin_name}':")
    for var in missing_vars:
        cli_logger.error(f"  • {var}")
    cli_logger.info(f"Run 'atk setup \"{plugin_name}\"' to configure.")


def _run_lifecycle_cli(
    command_name: LifecycleCommand,
    plugin: str | None,
    all_plugins: bool,
    reverse: bool = False,
) -> None:
    """Run a lifecycle command from CLI with proper output and exit codes."""
    atk_home = require_ready_home()
    verb = PAST_TENSE.get(command_name, command_name.capitalize() + "ed")

    if all_plugins and plugin:
        cli_logger.error("Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        cli_logger.error("Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if all_plugins:
        _run_all_plugins_lifecycle_cli(atk_home, command_name, verb, reverse=reverse)
    else:
        assert plugin is not None
        _run_single_plugin_lifecycle_cli(atk_home, plugin, command_name, verb)


def _run_single_plugin_lifecycle_cli(
    atk_home: Path, identifier: str, command_name: LifecycleCommand, verb: str
) -> None:
    """Run lifecycle command for a single plugin and format output."""
    result = execute_lifecycle(atk_home, identifier, command_name)

    match result:
        case LifecycleSuccess(plugin_name=name):
            cli_logger.success(f"{verb} plugin '{name}'")
            raise typer.Exit(exit_codes.SUCCESS)

        case LifecycleCommandFailed(plugin_name=name, exit_code=code):
            cli_logger.error(
                f"{command_name.capitalize()} failed for plugin '{name}' (exit code {code})"
            )
            raise typer.Exit(code)

        case LifecycleCommandSkipped(plugin_name=name, command_name=cmd):
            cli_logger.warning(f"Plugin '{name}' has no {cmd} command defined")
            raise typer.Exit(exit_codes.SUCCESS)

        case LifecyclePluginNotFound(identifier=ident):
            cli_logger.error(f"Plugin '{ident}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND)

        case LifecycleMissingEnvVars(plugin_name=name, missing_vars=missing):
            _format_missing_env_vars(name, missing)
            raise typer.Exit(exit_codes.ENV_NOT_CONFIGURED)

        case LifecyclePortConflict(plugin_name=name, conflicts=conflicts):
            _format_port_conflicts(name, conflicts)
            raise typer.Exit(exit_codes.PORT_CONFLICT)


def _format_port_conflicts(plugin_name: str, conflicts: list[PortConflict]) -> None:
    """Format port conflict error messages."""
    for conflict in conflicts:
        cli_logger.error(f"Port {conflict.port} is already in use")
        if conflict.description:
            cli_logger.error(f"  {plugin_name} requires this port for: {conflict.description}")
    cli_logger.info(
        "Stop the conflicting service or use 'atk restart' if the plugin is already running."
    )


def _run_all_plugins_lifecycle_cli(
    atk_home: Path, command_name: LifecycleCommand, verb: str, *, reverse: bool
) -> None:
    """Run lifecycle command for all plugins and format output."""
    result = execute_all_lifecycle(atk_home, command_name, reverse=reverse)

    match result:
        case AllPluginsSuccess(succeeded=succeeded, skipped=skipped):
            for name in succeeded:
                cli_logger.success(f"{verb} plugin '{name}'")
            for name in skipped:
                cli_logger.warning(f"Plugin '{name}' has no {command_name} command defined")
            raise typer.Exit(exit_codes.SUCCESS)

        case AllPluginsPartialFailure(succeeded=succeeded, skipped=skipped, failed=failed):
            for name in succeeded:
                cli_logger.success(f"{verb} plugin '{name}'")
            for name in skipped:
                cli_logger.warning(f"Plugin '{name}' has no {command_name} command defined")
            for name, code in failed:
                cli_logger.error(
                    f"{command_name.capitalize()} failed for plugin '{name}' (exit code {code})"
                )
            raise typer.Exit(exit_codes.GENERAL_ERROR)

        case AllPluginsMissingEnvVars(plugin_name=name, missing_vars=missing):
            _format_missing_env_vars(name, missing)
            raise typer.Exit(exit_codes.ENV_NOT_CONFIGURED)

        case AllPluginsPortConflict(plugin_name=name, conflicts=conflicts):
            _format_port_conflicts(name, conflicts)
            raise typer.Exit(exit_codes.PORT_CONFLICT)


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
def add(
    source: Annotated[
        str,
        typer.Argument(
            help="Plugin source: local path, registry name, or git URL.",
        ),
    ],
) -> None:
    """Add a plugin to ATK Home.

    Accepts a local path, registry plugin name, or git URL.
    If the plugin has environment variables, prompts for configuration before install.
    """
    atk_home = require_ready_home()

    try:
        directory = add_plugin(source, atk_home, _stdin_prompt)
        cli_logger.success(f"Added plugin to {atk_home}/plugins/{directory}")
        raise typer.Exit(exit_codes.SUCCESS)
    except RegistryPluginNotFoundError as e:
        cli_logger.error(f"Plugin not found in registry: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e
    except InstallFailedError as e:
        cli_logger.error(f"Install failed for plugin '{e.plugin_name}' (exit code {e.exit_code})")
        raise typer.Exit(exit_codes.DOCKER_ERROR) from e
    except (ValueError, FileNotFoundError) as e:
        cli_logger.error(f"Failed to add plugin: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e
    except GitPluginNotFoundError as e:
        cli_logger.error(f"Git repo does not contain an ATK plugin: {e}")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from e
    except GitSourceError as e:
        cli_logger.error(f"Failed to fetch from git: {e}")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from e


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
            # Plugin not in manifest — remove_plugin will handle as no-op
            pass

    try:
        result = remove_plugin(plugin, atk_home, force=force)
        if result.removed:
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
    atk_home = require_ready_home()

    if all_plugins and plugin:
        cli_logger.error("Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        cli_logger.error("Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if plugin:
        _upgrade_single_plugin(atk_home, plugin)
    else:
        _upgrade_all_plugins(atk_home)


def _upgrade_single_plugin(atk_home: Path, identifier: str) -> None:
    """Upgrade a single plugin and format output."""
    try:
        result = upgrade_plugin(identifier, atk_home, _stdin_prompt)
    except LocalPluginError:
        cli_logger.error(f"Plugin '{identifier}' is a local plugin and cannot be upgraded")
        raise typer.Exit(exit_codes.PLUGIN_INVALID) from None
    except UpgradeError as e:
        cli_logger.error(f"Upgrade failed: {e}")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from None
    except GitSourceError as e:
        cli_logger.error(f"Failed to fetch from git: {e}")
        raise typer.Exit(exit_codes.GENERAL_ERROR) from None

    if not result.upgraded:
        cli_logger.info(f"Plugin '{result.plugin_name}' is already up to date")
        raise typer.Exit(exit_codes.SUCCESS)

    cli_logger.success(f"Upgraded plugin '{result.plugin_name}'")
    if result.new_env_vars:
        cli_logger.info(f"  New environment variables configured: {', '.join(result.new_env_vars)}")
    if result.install_failed:
        cli_logger.error(
            f"  Install failed (exit code {result.install_exit_code})"
        )
        raise typer.Exit(exit_codes.GENERAL_ERROR)
    raise typer.Exit(exit_codes.SUCCESS)


def _upgrade_all_plugins(atk_home: Path) -> None:
    """Upgrade all upgradeable plugins and format output."""
    manifest = load_manifest(atk_home)
    upgraded_count = 0
    skipped_count = 0
    failed_count = 0

    for entry in manifest.plugins:
        if entry.source.type == SourceType.LOCAL:
            cli_logger.dim(f"Skipping local plugin '{entry.name}'")
            skipped_count += 1
            continue

        try:
            result = upgrade_plugin(entry.directory, atk_home, _stdin_prompt)
        except (UpgradeError, GitSourceError) as e:
            cli_logger.error(f"Failed to upgrade '{entry.name}': {e}")
            failed_count += 1
            continue

        if not result.upgraded:
            cli_logger.dim(f"Plugin '{result.plugin_name}' is already up to date")
            continue

        cli_logger.success(f"Upgraded plugin '{result.plugin_name}'")
        if result.new_env_vars:
            cli_logger.info(f"  New environment variables: {', '.join(result.new_env_vars)}")
        if result.install_failed:
            cli_logger.error(f"  Install failed (exit code {result.install_exit_code})")
            failed_count += 1
        else:
            upgraded_count += 1

    # Summary
    if upgraded_count == 0 and failed_count == 0:
        cli_logger.info("All plugins are up to date")
    elif failed_count > 0:
        cli_logger.error(f"Upgrade complete: {upgraded_count} upgraded, {failed_count} failed")
        raise typer.Exit(exit_codes.GENERAL_ERROR)

    raise typer.Exit(exit_codes.SUCCESS)


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

    if all_plugins and plugin:
        cli_logger.error("Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        cli_logger.error("Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if plugin:
        try:
            plugin_schema, plugin_dir = load_plugin(atk_home, plugin)
        except PluginNotFoundError:
            cli_logger.error(f"Plugin '{plugin}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

        if not plugin_schema.env_vars:
            cli_logger.info(f"Plugin '{plugin_schema.name}' has no environment variables defined")
            raise typer.Exit(exit_codes.SUCCESS)

        result = run_setup(plugin_schema, plugin_dir, _stdin_prompt)
        cli_logger.success(f"Configured {len(result.configured_vars)} variable(s) for '{result.plugin_name}'")
        raise typer.Exit(exit_codes.SUCCESS)

    manifest = load_manifest(atk_home)
    for plugin_entry in manifest.plugins:
        plugin_schema, plugin_dir = load_plugin(atk_home, plugin_entry.directory)
        if not plugin_schema.env_vars:
            continue
        cli_logger.info(f"\nConfiguring '{plugin_schema.name}':")
        result = run_setup(plugin_schema, plugin_dir, _stdin_prompt)
        cli_logger.success(f"Configured {len(result.configured_vars)} variable(s)")

    raise typer.Exit(exit_codes.SUCCESS)


@app.command()
def mcp(
    plugin: Annotated[
        str,
        typer.Argument(
            help="Plugin name or directory to get MCP config for.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON instead of plaintext."),
    ] = False,
) -> None:
    """Output MCP configuration for a plugin.

    Reads the MCP config from plugin.yaml and resolves environment variables
    from the plugin's .env file. Output can be copied into IDE/tool configurations.
    """
    import json

    atk_home = require_ready_home()

    try:
        plugin_schema, plugin_dir = load_plugin(atk_home, plugin)
    except PluginNotFoundError:
        cli_logger.error(f"Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

    if plugin_schema.mcp is None:
        cli_logger.error(f"Plugin '{plugin_schema.name}' has no MCP configuration")
        raise typer.Exit(exit_codes.PLUGIN_INVALID)

    result = generate_mcp_config(plugin_schema, plugin_dir, plugin_schema.name)

    if result.missing_vars:
        for var in result.missing_vars:
            cli_logger.warning(f"Environment variable '{var}' is not set")

    if json_output:
        print(json.dumps(result.config, indent=2))
    else:
        console.print(format_mcp_plaintext(result))

    raise typer.Exit(exit_codes.SUCCESS)


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

    # Load plugin to get schema
    try:
        plugin_schema, plugin_dir = load_plugin(atk_home, plugin)
    except PluginNotFoundError:
        cli_logger.error(f"Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

    # Check if uninstall is defined
    if plugin_schema.lifecycle is None or plugin_schema.lifecycle.uninstall is None:
        cli_logger.warning(f"Plugin '{plugin_schema.name}' has no uninstall command defined")
        raise typer.Exit(exit_codes.SUCCESS)

    # Show confirmation prompt unless --force
    if not force:
        console.print(
            f"\n⚠️  This will run the uninstall command which may delete data:\n"
            f"    {plugin_schema.lifecycle.uninstall}\n",
            style="yellow",
        )
        confirm = typer.confirm("Continue?", default=False)
        if not confirm:
            cli_logger.info("Uninstall cancelled")
            raise typer.Exit(exit_codes.SUCCESS)

    # Run stop lifecycle first (if defined)
    from atk.lifecycle import LifecycleCommandNotDefinedError, run_lifecycle_command

    try:
        exit_code = run_lifecycle_command(plugin_schema, plugin_dir, "stop")
        if exit_code != 0:
            cli_logger.warning(f"Stop failed with exit code {exit_code}, continuing with uninstall")
    except LifecycleCommandNotDefinedError:
        # Stop is optional, continue
        pass

    # Run uninstall lifecycle
    try:
        exit_code = run_lifecycle_command(plugin_schema, plugin_dir, "uninstall")
        if exit_code != 0:
            cli_logger.error(f"Uninstall failed with exit code {exit_code}")
            raise typer.Exit(exit_codes.DOCKER_ERROR)
        cli_logger.success(f"Uninstalled '{plugin_schema.name}'")
        raise typer.Exit(exit_codes.SUCCESS)
    except LifecycleCommandNotDefinedError as e:
        # Should not happen since we checked above, but handle gracefully
        cli_logger.warning(f"Plugin '{plugin_schema.name}' has no uninstall command defined")
        raise typer.Exit(exit_codes.SUCCESS) from e


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
    """Restart a plugin by executing stop then start.

    For a single plugin: Executes stop then start in sequence.
    If stop fails, start is not attempted.

    For --all: Stops all plugins in reverse order, then starts all in
    manifest order. If the stop phase has failures, the start phase is skipped.
    """
    # Single plugin case - execute stop then start
    if plugin and not all_plugins:
        atk_home = require_ready_home()

        try:
            # Phase 1: Stop
            try:
                stop_code = run_plugin_lifecycle(atk_home, plugin, "stop")
                if stop_code == 0:
                    cli_logger.success(f"Stopped plugin '{plugin}'")
                else:
                    cli_logger.error(f"Stop failed for plugin '{plugin}' (exit code {stop_code})")
                    raise typer.Exit(exit_codes.GENERAL_ERROR)
            except LifecycleCommandNotDefinedError:
                cli_logger.warning(f"Plugin '{plugin}' has no stop command defined")

            # Phase 2: Start
            try:
                start_code = run_plugin_lifecycle(atk_home, plugin, "start")
                if start_code == 0:
                    cli_logger.success(f"Started plugin '{plugin}'")
                    raise typer.Exit(exit_codes.SUCCESS)
                else:
                    cli_logger.error(f"Start failed for plugin '{plugin}' (exit code {start_code})")
                    raise typer.Exit(exit_codes.GENERAL_ERROR)
            except LifecycleCommandNotDefinedError:
                cli_logger.warning(f"Plugin '{plugin}' has no start command defined")
                raise typer.Exit(exit_codes.SUCCESS) from None

        except PluginNotFoundError:
            cli_logger.error(f"Plugin '{plugin}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None
        return

    # --all case - custom two-phase handling
    if all_plugins and plugin:
        cli_logger.error("Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        cli_logger.error("Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

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
            _print_status_table([result])
            raise typer.Exit(exit_codes.SUCCESS)
        except PluginNotFoundError:
            cli_logger.error(f"Plugin '{plugin}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

    # All plugins status
    results = get_all_plugins_status(atk_home)

    if not results:
        cli_logger.dim("No plugins installed.")
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
        cli_logger.error(f"Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None
    except LifecycleCommandNotDefinedError:
        cli_logger.warning(f"Plugin '{plugin}' has no logs command defined")
        raise typer.Exit(exit_codes.SUCCESS) from None



def _resolve_script(plugin_dir: Path, script: str) -> Path | None:
    """Resolve a script path, checking custom/ directory first.

    Resolution order:
    1. plugins/<plugin>/custom/<script>
    2. plugins/<plugin>/custom/<script>.sh
    3. plugins/<plugin>/<script>
    4. plugins/<plugin>/<script>.sh
    """
    custom_dir = plugin_dir / CUSTOM_DIR
    candidates = [
        custom_dir / script,
        custom_dir / f"{script}.sh",
        plugin_dir / script,
        plugin_dir / f"{script}.sh",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None



@app.command()
def run(
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
    """
    import subprocess

    atk_home = require_initialized_home()

    try:
        _, plugin_dir = load_plugin(atk_home, plugin)
    except PluginNotFoundError:
        cli_logger.error(f"Plugin '{plugin}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None

    script_path = _resolve_script(plugin_dir, script)
    if script_path is None:
        cli_logger.error(f"Script '{script}' not found in plugin directory")
        raise typer.Exit(exit_codes.GENERAL_ERROR)

    env_file = plugin_dir / ".env"
    merged_env = {**os.environ, **load_env_file(env_file)}
    result = subprocess.run(
        [str(script_path)],
        cwd=plugin_dir,
        env=merged_env,
    )
    raise typer.Exit(result.returncode)


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


def format_env_status(
    missing_required_vars: list[str], unset_optional_count: int, total_env_vars: int
) -> str:
    """Format environment variable status for display.

    Args:
        missing_required_vars: List of missing required variable names.
        unset_optional_count: Count of unset optional variables.
        total_env_vars: Total number of env vars defined in plugin.yaml.

    Returns:
        Formatted string:
        - "✓" if all required vars are set
        - "! VAR1, VAR2 (+N optional)" if required vars missing
        - "-" if no env vars defined
    """
    # No env vars defined
    if total_env_vars == 0:
        return "-"

    # All required vars set
    if not missing_required_vars:
        return "[green]✓[/green]"

    # Missing required vars
    var_list = ", ".join(missing_required_vars)
    result = f"[red]! {var_list}[/red]"

    # Add optional count if any
    if unset_optional_count > 0:
        result += f" [dim](+{unset_optional_count} optional)[/dim]"

    return result


def _print_status_table(results: list[PluginStatusResult]) -> None:
    """Print a status table for the given plugin status results."""

    table = Table(show_header=True, header_style="bold")
    table.add_column("NAME", style="cyan")
    table.add_column("STATUS")
    table.add_column("PORTS")
    table.add_column("ENV")

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

        # Format ENV column
        env_str = format_env_status(
            result.missing_required_vars, result.unset_optional_count, result.total_env_vars
        )

        name = f"{result.name} ({result.directory})"

        table.add_row(name, status_str, ports_str, env_str)

    console.print(table)

    # Print legend
    has_port_checks = any(
        p.listening is not None for r in results for p in r.ports
    )
    has_env_vars = any(r.total_env_vars > 0 for r in results)

    if has_port_checks or has_env_vars:
        console.print()
        console.print("[dim]Legend:[/dim]")

        if has_port_checks:
            console.print("[dim]  Ports: [/dim][green]✓[/green][dim] listening, [/dim][red]✗[/red][dim] not listening[/dim]")

        if has_env_vars:
            console.print(
                "[dim]  ENV: [/dim][green]✓[/green][dim] all required vars set, "
                "[/dim][red]![/red][dim] missing required vars, [/dim]-[dim] no env vars defined[/dim]"
            )

        if has_port_checks:
            console.print()
            console.print("[dim]Note: Port checks verify if something is listening, not that it's the plugin.[/dim]")


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

