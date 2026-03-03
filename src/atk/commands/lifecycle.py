"""Lifecycle command orchestration and output formatting.

Contains the runners that bridge the CLI layer to atk.lifecycle,
and all display helpers for lifecycle results.
"""

from pathlib import Path

import typer
from rich.console import Console

from atk import cli_logger, exit_codes
from atk.commands.preconditions import assert_plugin_or_all, require_ready_home
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
    PortConflict,
    execute_all_lifecycle,
    execute_lifecycle,
    run_lifecycle_command,
)
from atk.plugin_schema import PluginSchema

console = Console()

PAST_TENSE: dict[str, str] = {
    "install": "Installed",
    "start": "Started",
    "stop": "Stopped",
    "restart": "Restarted",
}


def format_missing_env_vars(plugin_name: str, missing_vars: list[str]) -> None:
    """Output error message for missing required env vars."""
    cli_logger.error(f"Missing required environment variables for '{plugin_name}':")
    for var in missing_vars:
        cli_logger.error(f"  • {var}")
    cli_logger.info(f"Run 'atk setup \"{plugin_name}\"' to configure.")


def format_port_conflicts(plugin_name: str, conflicts: list[PortConflict]) -> None:
    """Format port conflict error messages."""
    for conflict in conflicts:
        cli_logger.error(f"Port {conflict.port} is already in use")
        if conflict.description:
            cli_logger.error(f"  {plugin_name} requires this port for: {conflict.description}")
    cli_logger.info(
        "Stop the conflicting service or use 'atk restart' if the plugin is already running."
    )


def run_single_plugin_lifecycle_cli(
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
            format_missing_env_vars(name, missing)
            raise typer.Exit(exit_codes.ENV_NOT_CONFIGURED)

        case LifecyclePortConflict(plugin_name=name, conflicts=conflicts):
            format_port_conflicts(name, conflicts)
            raise typer.Exit(exit_codes.PORT_CONFLICT)


def run_all_plugins_lifecycle_cli(
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
            format_missing_env_vars(name, missing)
            raise typer.Exit(exit_codes.ENV_NOT_CONFIGURED)

        case AllPluginsPortConflict(plugin_name=name, conflicts=conflicts):
            format_port_conflicts(name, conflicts)
            raise typer.Exit(exit_codes.PORT_CONFLICT)


def run_lifecycle_cli(
    command_name: LifecycleCommand,
    plugin: str | None,
    all_plugins: bool,
    reverse: bool = False,
) -> None:
    """Run a lifecycle command from CLI with proper output and exit codes."""
    atk_home = require_ready_home()
    verb = PAST_TENSE.get(command_name, command_name.capitalize() + "ed")

    assert_plugin_or_all(plugin, all_plugins)

    if all_plugins:
        run_all_plugins_lifecycle_cli(atk_home, command_name, verb, reverse=reverse)
    else:
        assert plugin is not None
        run_single_plugin_lifecycle_cli(atk_home, plugin, command_name, verb)



def run_uninstall_cli(
    plugin_schema: PluginSchema,
    plugin_dir: Path,
    *,
    force: bool = False,
) -> None:
    """Run the uninstall lifecycle for a plugin with confirmation and stop phase.

    Checks whether an uninstall command is defined, optionally shows a
    confirmation prompt, runs stop (if defined, failure is non-fatal), then
    runs uninstall.

    Args:
        plugin_schema: Loaded plugin schema.
        plugin_dir: Path to the plugin directory.
        force: Skip confirmation prompt.

    Raises:
        typer.Exit: With SUCCESS or DOCKER_ERROR exit codes.
    """
    if plugin_schema.lifecycle is None or plugin_schema.lifecycle.uninstall is None:
        cli_logger.warning(f"Plugin '{plugin_schema.name}' has no uninstall command defined")
        raise typer.Exit(exit_codes.SUCCESS)

    if not force:
        console.print(
            f"\n⚠️  This will run the uninstall command which may delete data:\n"
            f"    {plugin_schema.lifecycle.uninstall}\n",
            style="yellow",
        )
        if not typer.confirm("Continue?", default=False):
            cli_logger.info("Uninstall cancelled")
            raise typer.Exit(exit_codes.SUCCESS)

    # Run stop lifecycle first — failure is non-fatal
    try:
        stop_code = run_lifecycle_command(plugin_schema, plugin_dir, "stop")
        if stop_code != 0:
            cli_logger.warning(f"Stop failed with exit code {stop_code}, continuing with uninstall")
    except LifecycleCommandNotDefinedError:
        pass

    # Run uninstall lifecycle
    try:
        exit_code = run_lifecycle_command(plugin_schema, plugin_dir, "uninstall")
    except LifecycleCommandNotDefinedError:
        # Should not happen since we checked above, but handle gracefully
        cli_logger.warning(f"Plugin '{plugin_schema.name}' has no uninstall command defined")
        raise typer.Exit(exit_codes.SUCCESS) from None

    if exit_code != 0:
        cli_logger.error(f"Uninstall failed with exit code {exit_code}")
        raise typer.Exit(exit_codes.DOCKER_ERROR)

    cli_logger.success(f"Uninstalled '{plugin_schema.name}'")
    raise typer.Exit(exit_codes.SUCCESS)


def run_restart_single_cli(atk_home: Path, identifier: str) -> None:
    """Run stop then start for a single plugin, reporting each phase.

    Uses the same execute_lifecycle infrastructure as all other lifecycle
    commands so env-var and port-conflict checks are applied to the start
    phase automatically.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory.

    Raises:
        typer.Exit: With SUCCESS, GENERAL_ERROR, or PLUGIN_NOT_FOUND.
    """
    # Phase 1: Stop
    stop_result = execute_lifecycle(atk_home, identifier, "stop")
    match stop_result:
        case LifecycleSuccess(plugin_name=name):
            cli_logger.success(f"Stopped plugin '{name}'")
        case LifecycleCommandFailed(plugin_name=name, exit_code=code):
            cli_logger.error(f"Stop failed for plugin '{name}' (exit code {code})")
            raise typer.Exit(exit_codes.GENERAL_ERROR)
        case LifecycleCommandSkipped(plugin_name=name):
            cli_logger.warning(f"Plugin '{name}' has no stop command defined")
        case LifecyclePluginNotFound(identifier=ident):
            cli_logger.error(f"Plugin '{ident}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND)
        case LifecycleMissingEnvVars(plugin_name=name, missing_vars=missing):
            format_missing_env_vars(name, missing)
            raise typer.Exit(exit_codes.ENV_NOT_CONFIGURED)
        case LifecyclePortConflict(plugin_name=name, conflicts=conflicts):
            format_port_conflicts(name, conflicts)
            raise typer.Exit(exit_codes.PORT_CONFLICT)

    # Phase 2: Start
    start_result = execute_lifecycle(atk_home, identifier, "start")
    match start_result:
        case LifecycleSuccess(plugin_name=name):
            cli_logger.success(f"Started plugin '{name}'")
            raise typer.Exit(exit_codes.SUCCESS)
        case LifecycleCommandFailed(plugin_name=name, exit_code=code):
            cli_logger.error(f"Start failed for plugin '{name}' (exit code {code})")
            raise typer.Exit(exit_codes.GENERAL_ERROR)
        case LifecycleCommandSkipped(plugin_name=name):
            cli_logger.warning(f"Plugin '{name}' has no start command defined")
            raise typer.Exit(exit_codes.SUCCESS)
        case LifecyclePluginNotFound(identifier=ident):
            cli_logger.error(f"Plugin '{ident}' not found in manifest")
            raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND)
        case LifecycleMissingEnvVars(plugin_name=name, missing_vars=missing):
            format_missing_env_vars(name, missing)
            raise typer.Exit(exit_codes.ENV_NOT_CONFIGURED)
        case LifecyclePortConflict(plugin_name=name, conflicts=conflicts):
            format_port_conflicts(name, conflicts)
            raise typer.Exit(exit_codes.PORT_CONFLICT)
