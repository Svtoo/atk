"""Pre-flight guards and shared CLI helpers.

Functions here verify that the environment is ready before any command
runs, and provide shared input/output utilities used across commands.
"""

from pathlib import Path

import typer

from atk import cli_logger, exit_codes
from atk.git import is_git_available
from atk.home import get_atk_home, validate_atk_home
from atk.manifest_schema import load_manifest
from atk.plugin import PluginNotFoundError, load_plugin
from atk.plugin_schema import PluginSchema


def stdin_prompt(text: str) -> str:
    """Prompt the user for input via stdin."""
    return input(text)


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

    manifest = load_manifest(atk_home)
    if manifest.config.auto_commit:
        require_git()

    return atk_home


def require_plugin(atk_home: Path, identifier: str) -> tuple[PluginSchema, Path]:
    """Load a plugin or exit with PLUGIN_NOT_FOUND.

    Centralises the repeated pattern of calling load_plugin and converting a
    PluginNotFoundError into a clean CLI exit so individual commands stay thin.

    Args:
        atk_home: Path to ATK Home directory.
        identifier: Plugin name or directory name.

    Returns:
        (plugin_schema, plugin_dir) tuple.

    Raises:
        typer.Exit: With PLUGIN_NOT_FOUND exit code if the plugin is not found.
    """
    try:
        return load_plugin(atk_home, identifier)
    except PluginNotFoundError:
        cli_logger.error(f"Plugin '{identifier}' not found in manifest")
        raise typer.Exit(exit_codes.PLUGIN_NOT_FOUND) from None


def assert_plugin_or_all(plugin: str | None, all_plugins: bool) -> None:
    """Validate that exactly one of plugin or --all is specified.

    Raises:
        typer.Exit: With INVALID_ARGS if both or neither are provided.
    """
    if all_plugins and plugin:
        cli_logger.error("Cannot specify both plugin and --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

    if not all_plugins and not plugin:
        cli_logger.error("Must specify plugin or --all")
        raise typer.Exit(exit_codes.INVALID_ARGS)

