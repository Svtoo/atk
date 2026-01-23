"""Manifest schema definitions using Pydantic.

This module defines the schema for manifest.yaml files that track
installed plugins in ATK Home.
"""

import re

from pydantic import BaseModel, Field, field_validator

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

