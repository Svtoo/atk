"""ATK Home initialization.

Provides functionality to create and initialize an ATK Home directory
with the required structure, git repository, and initial commit.
"""

import subprocess
from pathlib import Path

import yaml

from atk.git import git_add, git_commit, git_init
from atk.home import validate_atk_home
from atk.manifest_schema import (
    MANIFEST_SCHEMA_VERSION,
    ConfigSection,
    ManifestSchema,
)
from atk.validation import ValidationResult


def _create_initial_manifest() -> str:
    """Create initial manifest content from Pydantic model.

    This ensures the manifest is always valid according to schema.
    """
    manifest = ManifestSchema(
        schema_version=MANIFEST_SCHEMA_VERSION,
        config=ConfigSection(auto_commit=True),
        plugins=[],
    )
    return yaml.dump(manifest.model_dump(), default_flow_style=False, sort_keys=False)

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
        manifest_content = _create_initial_manifest()
        (path / "manifest.yaml").write_text(manifest_content)

        # Write .gitignore
        (path / ".gitignore").write_text(GITIGNORE_CONTENT)

        # Initialize git repository
        git_init(path)
        git_add(path)
        git_commit(path, "Initialize ATK Home")

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
