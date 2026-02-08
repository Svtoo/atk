"""Manifest schema definitions using Pydantic.

This module defines the schema for manifest.yaml files that track
installed plugins in ATK Home.
"""

import re
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from atk.errors import format_validation_errors

# Schema version - update when manifest schema changes
MANIFEST_SCHEMA_VERSION = "2026-02-06"

# Directory name validation regex per atk-home-spec.md
# Rules: lowercase, alphanumeric + hyphens, starts with letter,
# ends with alphanumeric, no consecutive hyphens, minimum 2 chars
DIRECTORY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

class SourceType(str, Enum):
    """Type of plugin source."""

    LOCAL = "local"
    REGISTRY = "registry"
    GIT = "git"


class SourceInfo(BaseModel):
    """Source metadata for a plugin entry.

    Tracks where a plugin came from and its pinned version.
    """

    type: SourceType = SourceType.LOCAL
    ref: str | None = Field(default=None, description="Commit hash for version pinning")
    url: str | None = Field(default=None, description="Git URL (for git sources)")


class PluginEntry(BaseModel):
    """Entry for an installed plugin in the manifest."""

    name: str = Field(description="Display name (user-friendly, any format)")
    directory: str = Field(description="Sanitized directory name")
    source: SourceInfo = Field(default_factory=lambda: SourceInfo())

    @field_validator("directory")
    @classmethod
    def validate_directory(cls, v: str) -> str:
        """Validate directory name follows naming rules."""
        if len(v) < 2:
            msg = "directory must be at least 2 characters"
            raise ValueError(msg)
        if not DIRECTORY_PATTERN.match(v):
            msg = (
                "directory must be lowercase, start with a letter, "
                "end with alphanumeric, and contain only letters, numbers, and single hyphens"
            )
            raise ValueError(msg)
        return v


class ConfigSection(BaseModel):
    """Configuration section of the manifest."""

    auto_commit: bool = Field(
        default=True,
        description="Commit after mutations (default: true)",
    )


class ManifestSchema(BaseModel):
    """Root schema for manifest.yaml files."""

    schema_version: str = Field(description="Schema version in YYYY-MM-DD format")
    config: ConfigSection = Field(
        default_factory=ConfigSection,
        description="Configuration settings",
    )
    plugins: list[PluginEntry] = Field(
        default_factory=list,
        description="List of installed plugins",
    )


def load_manifest(atk_home: Path) -> "ManifestSchema":
    """Load and validate manifest.yaml from ATK Home.

    Args:
        atk_home: Path to ATK Home directory.

    Returns:
        Validated ManifestSchema instance.

    Raises:
        FileNotFoundError: If manifest.yaml does not exist.
        ValueError: If YAML is invalid or schema validation fails.
    """
    manifest_path = atk_home / "manifest.yaml"
    if not manifest_path.exists():
        msg = f"manifest.yaml not found at {manifest_path}"
        raise FileNotFoundError(msg)

    content = manifest_path.read_text()
    data = yaml.safe_load(content)
    try:
        return ManifestSchema.model_validate(data)
    except ValidationError as e:
        clean_errors = format_validation_errors(e)
        msg = f"Invalid manifest '{manifest_path}': {clean_errors}"
        raise ValueError(msg) from e


def save_manifest(manifest: "ManifestSchema", atk_home: Path) -> None:
    """Save ManifestSchema to manifest.yaml in ATK Home.

    Args:
        manifest: ManifestSchema instance to save.
        atk_home: Path to ATK Home directory.
    """
    manifest_path = atk_home / "manifest.yaml"
    # Use mode="json" to serialize enums as their string values
    manifest_path.write_text(
        yaml.dump(manifest.model_dump(mode="json"), default_flow_style=False, sort_keys=False)
    )
