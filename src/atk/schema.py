"""Plugin YAML schema definitions using Pydantic.

This module defines the schema for plugin.yaml files that describe
how to install and manage AI development tools.
"""

from enum import Enum

from pydantic import BaseModel, Field


class ServiceType(str, Enum):
    """Supported service types for running plugins."""

    DOCKER_COMPOSE = "docker-compose"
    DOCKER = "docker"
    SYSTEMD = "systemd"
    SCRIPT = "script"


class ServiceConfig(BaseModel):
    """Configuration for how to run the plugin's service."""

    type: ServiceType = Field(
        default=ServiceType.DOCKER_COMPOSE,
        description="Type of service runner",
    )
    compose_file: str | None = Field(
        default=None,
        description="Path to docker-compose file (for docker-compose type)",
    )


class VendorConfig(BaseModel):
    """Configuration for cloning from an upstream repository."""

    url: str = Field(description="Git repository URL")
    ref: str = Field(description="Git ref (tag, branch, or commit)")


class PortConfig(BaseModel):
    """Configuration for a network port exposed by the plugin."""

    name: str = Field(description="Human-readable port name")
    port: int = Field(description="Port number")
    configurable: bool = Field(
        default=False,
        description="Whether the port can be changed during install",
    )
    health_endpoint: str | None = Field(
        default=None,
        description="HTTP GET endpoint for health checks",
    )


class EnvVarConfig(BaseModel):
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


class LifecycleConfig(BaseModel):
    """Configuration for lifecycle commands."""

    install: str | None = Field(
        default=None,
        description="Command to install/update the plugin",
    )
    start: str | None = Field(
        default=None,
        description="Command to start the service",
    )
    stop: str | None = Field(
        default=None,
        description="Command to stop the service",
    )
    restart: str | None = Field(
        default=None,
        description="Command to restart the service",
    )
    logs: str | None = Field(
        default=None,
        description="Command to view logs",
    )
    status: str | None = Field(
        default=None,
        description="Command to check status (exit 0 = running)",
    )


class McpConfig(BaseModel):
    """Configuration for MCP (Model Context Protocol) integration."""

    enabled: bool = Field(
        default=False,
        description="Whether MCP is enabled for this plugin",
    )
    type: str | None = Field(
        default=None,
        description="MCP transport type (http-proxy, stdio, binary)",
    )
    endpoint: str | None = Field(
        default=None,
        description="MCP endpoint URL (for http-proxy type)",
    )


class PluginSchema(BaseModel):
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

