"""Registry index schema definitions using Pydantic.

This module defines the schema for index.yaml files used by the ATK registry.
The registry is a curated collection of plugins that can be installed by name.
"""

from pydantic import BaseModel, Field

# Schema version - update when registry index schema changes
REGISTRY_SCHEMA_VERSION = "2026-01-23"


class RegistryPluginEntry(BaseModel):
    """Entry for a plugin in the registry index."""

    name: str = Field(description="Plugin identifier (directory name)")
    path: str = Field(description="Path within registry repo (e.g., plugins/openmemory)")
    description: str = Field(description="One-line description from plugin.yaml")


class RegistryIndexSchema(BaseModel):
    """Root schema for registry index.yaml files."""

    schema_version: str = Field(
        default=REGISTRY_SCHEMA_VERSION,
        description="Schema version in YYYY-MM-DD format",
    )
    plugins: list[RegistryPluginEntry] = Field(
        default_factory=list,
        description="List of available plugins",
    )

