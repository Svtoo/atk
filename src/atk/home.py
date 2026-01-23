"""ATK Home resolution and validation.

ATK Home is the local git-backed repository that stores the manifest
and all installed plugins.
"""

import os
from pathlib import Path

from atk.validation import ValidationResult

# Default ATK Home location
DEFAULT_ATK_HOME = Path.home() / ".atk"

# Environment variable for custom ATK Home location
ATK_HOME_ENV_VAR = "ATK_HOME"


class ATKHomeNotInitializedError(Exception):
    """Raised when ATK Home is not initialized."""

    def __init__(self, path: Path, errors: list[str] | None = None) -> None:
        """Initialize with the path that was checked."""
        self.path = path
        self.errors = errors or []
        error_details = "\n  - ".join(self.errors) if self.errors else ""
        message = f"ATK Home not initialized at {path}. Run 'atk init' first."
        if error_details:
            message += f"\nIssues found:\n  - {error_details}"
        super().__init__(message)


def get_atk_home() -> Path:
    """Get the ATK Home directory path.

    Resolution order:
    1. ATK_HOME environment variable (if set)
    2. Default: ~/.atk/

    Returns:
        Path to ATK Home directory.
    """
    env_value = os.environ.get(ATK_HOME_ENV_VAR)
    if env_value:
        return Path(env_value).expanduser()
    return DEFAULT_ATK_HOME


def validate_atk_home(path: Path) -> ValidationResult:
    """Validate a directory as an ATK Home.

    A valid ATK Home has:
    - The directory exists and is a directory
    - manifest.yaml file
    - plugins/ directory
    - .git directory (initialized as git repo)

    Args:
        path: Path to check.

    Returns:
        ValidationResult with is_valid=True if valid, otherwise is_valid=False
        with a list of specific error messages.
    """
    errors: list[str] = []

    if not path.exists():
        errors.append(f"Path does not exist: {path}")
        return ValidationResult(is_valid=False, errors=errors)

    if not path.is_dir():
        errors.append(f"Path is not a directory: {path}")
        return ValidationResult(is_valid=False, errors=errors)

    # Check required components
    if not (path / "manifest.yaml").exists():
        errors.append("Missing manifest.yaml file")

    if not (path / "plugins").is_dir():
        errors.append("Missing plugins/ directory")

    if not (path / ".git").is_dir():
        errors.append("Missing .git directory (not a git repository)")

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)

