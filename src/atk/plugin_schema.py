"""Plugin YAML schema definitions using Pydantic.

This module defines the schema for plugin.yaml files that describe
how to install and manage AI development tools.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")

# Schema version - update when plugin schema changes
PLUGIN_SCHEMA_VERSION = "2026-01-23"


class ServiceType(str, Enum):
    """Supported service types for running plugins."""

    DOCKER_COMPOSE = "docker-compose"
    DOCKER = "docker"
    SYSTEMD = "systemd"
    SCRIPT = "script"


class ServiceConfig(StrictModel):
    """Configuration for how to run the plugin's service."""

    type: ServiceType = Field(
        default=ServiceType.DOCKER_COMPOSE,
        description="Type of service runner",
    )
    compose_file: str | None = Field(
        default=None,
        description="Path to docker-compose file (for docker-compose type)",
    )
    unit_name: str | None = Field(
        default=None,
        description="Systemd unit name (for systemd type)",
    )


class VendorConfig(StrictModel):
    """Configuration for the plugin vendor/upstream source."""

    name: str = Field(description="Vendor name")
    url: str | None = Field(
        default=None,
        description="Vendor website URL",
    )
    docs: str | None = Field(
        default=None,
        description="Documentation URL",
    )


class PortConfig(StrictModel):
    """Configuration for a network port exposed by the plugin."""

    port: int = Field(description="Port number")
    name: str | None = Field(
        default=None,
        description="Human-readable port name",
    )
    protocol: str = Field(
        default="http",
        description="Protocol (http, https, tcp, etc.)",
    )
    description: str | None = Field(
        default=None,
        description="Port description",
    )


class EnvVarConfig(StrictModel):
    """Configuration for an environment variable."""

    name: str = Field(description="Environment variable name")
    required: bool = Field(
        default=False,
        description="Whether the variable must be set",
    )
    secret: bool = Field(
        default=False,
        description="Whether the variable contains sensitive data",
    )
    default: str | None = Field(
        default=None,
        description="Default value if not set",
    )
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )


class LifecycleConfig(StrictModel):
    """Configuration for lifecycle commands."""

    install: str | None = Field(
        default=None,
        description="Command to install/update the plugin",
    )
    uninstall: str | None = Field(
        default=None,
        description="Command to uninstall the plugin and clean up resources",
    )
    start: str | None = Field(
        default=None,
        description="Command to start the service",
    )
    stop: str | None = Field(
        default=None,
        description="Command to stop the service",
    )
    logs: str | None = Field(
        default=None,
        description="Command to view logs",
    )
    status: str | None = Field(
        default=None,
        description="Command to check status (exit 0 = running)",
    )
    health_endpoint: str | None = Field(
        default=None,
        description="Health check endpoint URL",
    )


class McpConfig(StrictModel):
    """Configuration for MCP (Model Context Protocol) integration."""

    transport: Literal["stdio", "sse"] = Field(
        description="Transport type: stdio (command-based) or sse (URL-based)",
    )
    command: str | None = Field(
        default=None,
        description="Command to run (for stdio transport)",
    )
    args: list[str] | None = Field(
        default=None,
        description="Command arguments (for stdio transport)",
    )
    endpoint: str | None = Field(
        default=None,
        description="SSE endpoint URL (for sse transport)",
    )
    env: list[str] | None = Field(
        default=None,
        description="Environment variable names to include in MCP config",
    )


class PluginSchema(StrictModel):
    """Root schema for plugin.yaml files."""

    schema_version: str = Field(
        description="Schema version in YYYY-MM-DD format",
    )
    name: str = Field(description="Plugin name")
    description: str = Field(description="Plugin description")

    service: ServiceConfig | None = Field(
        default=None,
        description="Service configuration",
    )
    vendor: VendorConfig | None = Field(
        default=None,
        description="Upstream repository configuration",
    )
    ports: list[PortConfig] = Field(
        default_factory=list,
        description="Network ports exposed by the plugin",
    )
    env_vars: list[EnvVarConfig] = Field(
        default_factory=list,
        description="Environment variables",
    )
    lifecycle: LifecycleConfig | None = Field(
        default=None,
        description="Lifecycle commands",
    )
    mcp: McpConfig | None = Field(
        default=None,
        description="MCP integration configuration",
    )

    @model_validator(mode="after")
    def validate_install_uninstall_pairing(self) -> "PluginSchema":
        """Validate that if install is defined, uninstall must also be defined."""
        if (
            self.lifecycle is not None
            and self.lifecycle.install is not None
            and self.lifecycle.uninstall is None
        ):
            msg = "If 'install' lifecycle is defined, 'uninstall' must also be required to ensure proper cleanup"
            raise ValueError(msg)
        return self

