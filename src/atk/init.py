"""ATK Home initialization.

Provides functionality to create and initialize an ATK Home directory
with the required structure, git repository, and initial commit.
"""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from atk.home import validate_atk_home
from atk.validation import ValidationResult

# Schema version for new manifest files
SCHEMA_VERSION = datetime.now(UTC).strftime("%Y-%m-%d")

# Initial manifest content
MANIFEST_TEMPLATE = """\
schema_version: "{schema_version}"
config:
  auto_commit: true
plugins: []
"""

# Gitignore content
GITIGNORE_CONTENT = """\
# Environment files with secrets
*.env
.env.*

# Local development
.DS_Store
"""


def init_atk_home(path: Path) -> ValidationResult:
    """Initialize an ATK Home directory.

    Creates the directory structure, initializes git, and creates initial commit.

    If the path already exists and is a valid ATK Home, this is a no-op.
    If the path exists but is not valid (has other content), returns error.

    Args:
        path: Target directory to initialize.

    Returns:
        ValidationResult indicating success or failure with error messages.
    """
    # Check if already a valid ATK Home
    if path.exists():
        validation = validate_atk_home(path)
        if validation.is_valid:
            # Already valid - idempotent success
            return ValidationResult(is_valid=True, errors=[])

        # Path exists but is not valid ATK Home
        if path.is_file():
            return ValidationResult(
                is_valid=False,
                errors=[f"Path exists but is a file, not a directory: {path}"],
            )

        # Directory exists with content but not a valid ATK Home
        # Check if it has any content that would conflict
        if any(path.iterdir()):
            return ValidationResult(
                is_valid=False,
                errors=[
                    f"Directory exists but is not a valid ATK Home: {path}",
                    *validation.errors,
                ],
            )

    # Create directory structure
    try:
        path.mkdir(parents=True, exist_ok=True)
        (path / "plugins").mkdir(exist_ok=True)

        # Write manifest.yaml
        manifest_content = MANIFEST_TEMPLATE.format(schema_version=SCHEMA_VERSION)
        (path / "manifest.yaml").write_text(manifest_content)

        # Write .gitignore
        (path / ".gitignore").write_text(GITIGNORE_CONTENT)

        # Initialize git repository
        _git_init(path)
        _git_add_all(path)
        _git_commit(path, "Initialize ATK Home")

        return ValidationResult(is_valid=True, errors=[])

    except OSError as e:
        return ValidationResult(
            is_valid=False,
            errors=[f"Failed to create directory structure: {e}"],
        )
    except subprocess.CalledProcessError as e:
        return ValidationResult(
            is_valid=False,
            errors=[f"Git operation failed: {e}"],
        )


def _git_init(path: Path) -> None:
    """Initialize a git repository."""
    subprocess.run(
        ["git", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _git_add_all(path: Path) -> None:
    """Stage all files for commit."""
    subprocess.run(
        ["git", "add", "-A"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def _git_commit(path: Path, message: str) -> None:
    """Create a commit with the given message."""
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "ATK",
            "GIT_AUTHOR_EMAIL": "atk@localhost",
            "GIT_COMMITTER_NAME": "ATK",
            "GIT_COMMITTER_EMAIL": "atk@localhost",
        },
    )

