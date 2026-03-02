"""Upgrade orchestration for the `atk upgrade` command."""

from pathlib import Path

import typer

from atk import cli_logger, exit_codes
from atk.commands.preconditions import stdin_prompt
from atk.git_source import GitSourceError
from atk.manifest_schema import SourceType, load_manifest
from atk.upgrade import LocalPluginError, UpgradeError, upgrade_plugin


def upgrade_single_plugin(atk_home: Path, identifier: str) -> None:
    """Upgrade a single plugin and format output."""
    try:
        result = upgrade_plugin(identifier, atk_home, stdin_prompt)
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
        cli_logger.info(
            f"  New environment variables configured: {', '.join(result.new_env_vars)}"
        )
    if result.install_failed:
        cli_logger.error(f"  Install failed (exit code {result.install_exit_code})")
        raise typer.Exit(exit_codes.GENERAL_ERROR)
    raise typer.Exit(exit_codes.SUCCESS)


def upgrade_all_plugins(atk_home: Path) -> None:
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
            result = upgrade_plugin(entry.directory, atk_home, stdin_prompt)
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

    if upgraded_count == 0 and failed_count == 0:
        cli_logger.info("All plugins are up to date")
    elif failed_count > 0:
        cli_logger.error(f"Upgrade complete: {upgraded_count} upgraded, {failed_count} failed")
        raise typer.Exit(exit_codes.GENERAL_ERROR)

    raise typer.Exit(exit_codes.SUCCESS)

