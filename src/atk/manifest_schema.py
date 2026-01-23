"""Manifest schema definitions using Pydantic.

This module defines the schema for manifest.yaml files that track
installed plugins in ATK Home.
"""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

# Schema version - update when manifest schema changes
MANIFEST_SCHEMA_VERSION = "2026-01-23"

# Directory name validation regex per atk-home-spec.md
# Rules: lowercase, alphanumeric + hyphens, starts with letter,
# ends with alphanumeric, no consecutive hyphens, minimum 2 chars
DIRECTORY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class PluginEntry(BaseModel):
    """Entry for an installed plugin in the manifest."""

    name: str = Field(description="Display name (user-friendly, any format)")
    directory: str = Field(description="Sanitized directory name")

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
    """
    manifest_path = atk_home / "manifest.yaml"
    if not manifest_path.exists():
        msg = f"manifest.yaml not found at {manifest_path}"
        raise FileNotFoundError(msg)

    content = manifest_path.read_text()
    data = yaml.safe_load(content)
    return ManifestSchema.model_validate(data)


def save_manifest(manifest: "ManifestSchema", atk_home: Path) -> None:
    """Save ManifestSchema to manifest.yaml in ATK Home.

    Args:
        manifest: ManifestSchema instance to save.
        atk_home: Path to ATK Home directory.
    """
    manifest_path = atk_home / "manifest.yaml"
    manifest_path.write_text(
        yaml.dump(manifest.model_dump(), default_flow_style=False, sort_keys=False)
    )
