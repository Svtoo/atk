"""Directory name sanitization for plugins.

Converts display names like "My Plugin" to valid directory names like "my-plugin".
"""

import re


def sanitize_directory_name(display_name: str) -> str:
    """Convert a display name to a valid plugin directory name.

    Rules:
    - Lowercase
    - Replace spaces and underscores with hyphens
    - Strip all characters except alphanumeric and hyphens
    - Collapse consecutive hyphens
    - Prefix with 'a' if starts with non-letter
    - Minimum 2 characters

    Args:
        display_name: The human-readable plugin name.

    Returns:
        A sanitized directory name matching ^[a-z][a-z0-9]*(-[a-z0-9]+)*$

    Raises:
        ValueError: If the name cannot be sanitized to a valid directory name.
    """
    # Trim and lowercase
    name = display_name.strip().lower()

    if not name:
        msg = f"Display name '{display_name}' cannot be sanitized: empty after trimming"
        raise ValueError(msg)

    # Replace spaces and underscores with hyphens
    name = re.sub(r"[ _]+", "-", name)

    # Strip all characters except alphanumeric and hyphens
    name = re.sub(r"[^a-z0-9-]", "", name)

    # Collapse consecutive hyphens
    name = re.sub(r"-+", "-", name)

    # Strip leading/trailing hyphens
    name = name.strip("-")

    if not name:
        msg = f"Display name '{display_name}' cannot be sanitized: empty after processing"
        raise ValueError(msg)

    # Prefix with 'a' if starts with non-letter
    if not name[0].isalpha():
        name = "a" + name

    # Check minimum length
    if len(name) < 2:
        msg = f"Display name '{display_name}' cannot be sanitized: result too short"
        raise ValueError(msg)

    return name

