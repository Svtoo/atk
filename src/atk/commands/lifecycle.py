"""Lifecycle command orchestration and output formatting.

Contains the runners that bridge the CLI layer to atk.lifecycle,
and all display helpers for lifecycle results.
"""

from pathlib import Path

import typer

from atk import cli_logger, exit_codes
from atk.commands.preconditions import assert_plugin_or_all, require_ready_home
from atk.lifecycle import (
    AllPluginsMissingEnvVars,
    AllPluginsPartialFailure,
    AllPluginsPortConflict,
    AllPluginsSuccess,
    LifecycleCommand,
    LifecycleCommandFailed,
    LifecycleCommandSkipped,
    LifecycleMissingEnvVars,
    LifecyclePluginNotFound,
    LifecyclePortConflict,
    LifecycleSuccess,
    PortConflict,
    execute_all_lifecycle,
    execute_lifecycle,
)

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

