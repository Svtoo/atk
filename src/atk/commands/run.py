"""Script execution logic for the `atk run` command."""

import os
import subprocess
from pathlib import Path

import typer

from atk import cli_logger, exit_codes
from atk.env import load_env_file
from atk.plugin import CUSTOM_DIR


def resolve_script(plugin_dir: Path, script: str) -> Path | None:
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


def run_plugin_script(plugin_dir: Path, script: str, extra_args: list[str]) -> None:
    """Resolve and execute a plugin script, forwarding extra arguments.

    Raises:
        typer.Exit: With GENERAL_ERROR if the script is not found, otherwise
                    with the subprocess return code.
    """
    script_path = resolve_script(plugin_dir, script)
    if script_path is None:
        cli_logger.error(f"Script '{script}' not found in plugin directory")
        raise typer.Exit(exit_codes.GENERAL_ERROR)

    env_file = plugin_dir / ".env"
    merged_env = {**os.environ, **load_env_file(env_file)}
    result = subprocess.run(
        [str(script_path), *extra_args],
        cwd=plugin_dir,
        env=merged_env,
    )
    raise typer.Exit(result.returncode)

