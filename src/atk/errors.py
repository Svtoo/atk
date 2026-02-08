"""Error formatting utilities for ATK.

Provides clean, user-friendly error messages from Pydantic validation errors
and other exceptions.
"""

import subprocess

import yaml
from pydantic import ValidationError

from atk import cli_logger, exit_codes


def format_validation_errors(error: ValidationError) -> str:
    """Format Pydantic ValidationError into clean, user-friendly message.

    Removes Pydantic-specific URLs and technical jargon, producing a message
    suitable for CLI output.

    Args:
        error: The Pydantic ValidationError to format.

    Returns:
        A clean, human-readable error message.
    """
    messages = []

    for err in error.errors():
        # Get the field path (e.g., "ports.0.name" or just "description")
        loc = ".".join(str(part) for part in err["loc"])

        # Get the error type and message
        error_type = err["type"]
        msg = err["msg"]

        # Format based on error type
        if error_type == "missing":
            messages.append(f"'{loc}': field is required")
        elif error_type == "string_type":
            messages.append(f"'{loc}': expected string")
        elif error_type == "list_type":
            messages.append(f"'{loc}': expected list")
        elif error_type == "int_type":
            messages.append(f"'{loc}': expected integer")
        elif error_type == "bool_type":
            messages.append(f"'{loc}': expected boolean")
        else:
            # For other types, use the message but clean it up
            # Remove "Field required" redundancy, just use our format
            clean_msg = msg.lower()
            messages.append(f"'{loc}': {clean_msg}")

    if len(messages) == 1:
        return messages[0]

    # Multiple errors: list them
    return "; ".join(messages)



def handle_cli_error(error: Exception) -> int:
    """Handle an unhandled exception at the CLI boundary.

    Formats the error into a clean user-friendly message and returns
    an appropriate exit code. This is the last line of defense — it
    prevents raw tracebacks from reaching the user.

    Args:
        error: The exception to handle.

    Returns:
        An exit code from exit_codes.
    """
    if isinstance(error, ValidationError):
        cli_logger.error(f"Invalid configuration: {format_validation_errors(error)}")
        return exit_codes.PLUGIN_INVALID

    if isinstance(error, subprocess.CalledProcessError):
        cmd_str = " ".join(str(c) for c in error.cmd) if isinstance(error.cmd, list) else str(error.cmd)
        cli_logger.error(f"Command failed (exit code {error.returncode}): {cmd_str}")
        return exit_codes.GENERAL_ERROR

    if isinstance(error, OSError):
        if error.filename:
            cli_logger.error(f"{error.strerror}: {error.filename}")
        else:
            cli_logger.error(str(error))
        return exit_codes.GENERAL_ERROR

    if isinstance(error, yaml.YAMLError):
        cli_logger.error(f"Invalid YAML: {error}")
        return exit_codes.GENERAL_ERROR

    cli_logger.error(f"Unexpected error: {error}")
    return exit_codes.GENERAL_ERROR