"""Plugin YAML schema definitions using Pydantic.

This module defines the schema for plugin.yaml files that describe
how to install and manage AI development tools.
"""

import re
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    """Base model that forbids extra fields."""

    model_config = ConfigDict(extra="forbid")

# Schema version - update when plugin schema changes
PLUGIN_SCHEMA_VERSION = "2026-01-23"


class PluginMaturity(str, Enum):
    """Plugin maturity level, reflecting trust and verification status.

    The default is AI_GENERATED — every plugin produced by AI tooling starts here.
    Promoting to a higher level requires a conscious human decision.

    Registry CI requires VERIFIED; any plugin submitted with a lower maturity
    will fail index generation and be blocked from the registry.
    """

    AI_GENERATED = "ai-generated"
    """Built by an AI agent. No human has reviewed or tested this plugin."""

    COMMUNITY = "community"
    """A human has authored or validated this plugin, but it is not in the
    official ATK registry."""

    VERIFIED = "verified"
    """Listed in the official ATK registry. Curated and tested by maintainers."""


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

    port: int = Field(ge=1, le=65535, description="Port number (1–65535)")
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


_ENV_VAR_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class EnvVarConfig(StrictModel):
    """Configuration for an environment variable."""

    name: str = Field(description="Environment variable name (POSIX: uppercase letters, digits, underscore; must not start with a digit)")

    @field_validator("name")
    @classmethod
    def validate_env_var_name(cls, v: str) -> str:
        """Enforce POSIX env var naming: ^[A-Z_][A-Z0-9_]*$."""
        if not _ENV_VAR_NAME_RE.match(v):
            msg = (
                f"Invalid environment variable name '{v}'. "
                "Names must match ^[A-Z_][A-Z0-9_]*$ "
                "(uppercase letters, digits, and underscores only; must not start with a digit)."
            )
            raise ValueError(msg)
        return v
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


class McpPluginConfig(StrictModel):
    """MCP integration declared in a plugin's plugin.yaml."""

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

    @model_validator(mode="after")
    def validate_transport_fields(self) -> "McpPluginConfig":
        """Enforce transport-specific field requirements.

        - stdio: command is required; endpoint must not be set.
        - sse:   endpoint is required; command and args must not be set.
        """
        if self.transport == "stdio":
            if self.command is None:
                raise ValueError("'command' is required when transport is 'stdio'")
            if self.endpoint is not None:
                raise ValueError("'endpoint' must not be set when transport is 'stdio'")
        elif self.transport == "sse":
            if self.endpoint is None:
                raise ValueError("'endpoint' is required when transport is 'sse'")
            if self.command is not None:
                raise ValueError("'command' must not be set when transport is 'sse'")
            if self.args is not None:
                raise ValueError("'args' must not be set when transport is 'sse'")
        return self


class PluginSchema(StrictModel):
    """Root schema for plugin.yaml files."""

    schema_version: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Schema version in YYYY-MM-DD format",
    )
    name: str = Field(description="Plugin name")
    description: str = Field(description="Plugin description")
    maturity: PluginMaturity = Field(
        default=PluginMaturity.AI_GENERATED,
        description=(
            "Plugin maturity level. Defaults to 'ai-generated' — any plugin produced by AI "
            "tooling starts here. Must be explicitly promoted by a human. "
            "Registry CI requires 'verified'."
        ),
    )

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
    mcp: McpPluginConfig | None = Field(
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

