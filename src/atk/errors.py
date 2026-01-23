"""Error formatting utilities for ATK.

Provides clean, user-friendly error messages from Pydantic validation errors
and other exceptions.
"""

from pydantic import ValidationError


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

