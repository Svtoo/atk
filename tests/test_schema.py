"""Tests for plugin YAML schema validation."""

import pytest

from atk.schema import (
    EnvVarConfig,
    LifecycleConfig,
    McpConfig,
    PluginSchema,
    PortConfig,
    ServiceConfig,
    ServiceType,
    VendorConfig,
)


class TestPluginSchemaMinimal:
    """Tests for minimal valid plugin schema."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.minimal_data = {
            "schema_version": "2026-01-22",
            "name": "test-plugin",
            "description": "A test plugin",
        }

    def test_minimal_schema_is_valid(self) -> None:
        """Verify that a minimal schema with only required fields is valid."""
        # Given
        data = self.minimal_data

        # When
        plugin = PluginSchema.model_validate(data)

        # Then
        assert plugin.schema_version == data["schema_version"]
        assert plugin.name == data["name"]
        assert plugin.description == data["description"]

    def test_schema_version_is_required(self) -> None:
        """Verify that schema_version is required."""
        # Given
        data = {"name": "test", "description": "test"}

        # When/Then
        with pytest.raises(ValueError, match="schema_version"):
            PluginSchema.model_validate(data)

    def test_name_is_required(self) -> None:
        """Verify that name is required."""
        # Given
        data = {"schema_version": "2026-01-22", "description": "test"}

        # When/Then
        with pytest.raises(ValueError, match="name"):
            PluginSchema.model_validate(data)

    def test_description_is_required(self) -> None:
        """Verify that description is required."""
        # Given
        data = {"schema_version": "2026-01-22", "name": "test"}

        # When/Then
        with pytest.raises(ValueError, match="description"):
            PluginSchema.model_validate(data)


class TestServiceConfig:
    """Tests for service configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.docker_compose_service = {
            "type": "docker-compose",
            "compose_file": "docker-compose.yml",
        }

    def test_docker_compose_service(self) -> None:
        """Verify docker-compose service type is valid."""
        # Given
        data = self.docker_compose_service

        # When
        service = ServiceConfig.model_validate(data)

        # Then
        assert service.type == ServiceType.DOCKER_COMPOSE
        assert service.compose_file == data["compose_file"]

    def test_service_type_enum_values(self) -> None:
        """Verify all service types are supported."""
        # Given
        expected_types = ["docker-compose", "docker", "systemd", "script"]

        # When/Then
        for type_str in expected_types:
            service = ServiceConfig.model_validate({"type": type_str})
            assert service.type.value == type_str


class TestVendorConfig:
    """Tests for vendor repository configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.vendor_data = {
            "url": "https://github.com/CaviraOSS/OpenMemory.git",
            "ref": "v1.2.3",
        }

    def test_vendor_config_valid(self) -> None:
        """Verify vendor config with URL and ref is valid."""
        # Given
        data = self.vendor_data

        # When
        vendor = VendorConfig.model_validate(data)

        # Then
        assert vendor.url == data["url"]
        assert vendor.ref == data["ref"]

    def test_vendor_url_is_required(self) -> None:
        """Verify that vendor URL is required."""
        # Given
        data = {"ref": "main"}

        # When/Then
        with pytest.raises(ValueError, match="url"):
            VendorConfig.model_validate(data)


class TestPortConfig:
    """Tests for port configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.port_data = {
            "name": "API",
            "port": 8787,
            "configurable": True,
            "health_endpoint": "/health",
        }

    def test_port_config_full(self) -> None:
        """Verify full port config is valid."""
        # Given
        data = self.port_data

        # When
        port = PortConfig.model_validate(data)

        # Then
        assert port.name == data["name"]
        assert port.port == data["port"]
        assert port.configurable == data["configurable"]
        assert port.health_endpoint == data["health_endpoint"]

    def test_port_config_minimal(self) -> None:
        """Verify minimal port config with defaults."""
        # Given
        data = {"name": "API", "port": 8080}

        # When
        port = PortConfig.model_validate(data)

        # Then
        assert port.name == data["name"]
        assert port.port == data["port"]
        # And - defaults
        assert port.configurable is False
        assert port.health_endpoint is None


class TestEnvVarConfig:
    """Tests for environment variable configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.env_var_data = {
            "name": "OPENAI_API_KEY",
            "required": True,
            "secret": True,
            "description": "OpenAI API key for embeddings",
        }

    def test_env_var_config_full(self) -> None:
        """Verify full env var config is valid."""
        # Given
        data = self.env_var_data

        # When
        env_var = EnvVarConfig.model_validate(data)

        # Then
        assert env_var.name == data["name"]
        assert env_var.required == data["required"]
        assert env_var.secret == data["secret"]
        assert env_var.description == data["description"]

    def test_env_var_config_minimal(self) -> None:
        """Verify minimal env var config with defaults."""
        # Given
        data = {"name": "MY_VAR"}

        # When
        env_var = EnvVarConfig.model_validate(data)

        # Then
        assert env_var.name == data["name"]
        # And - defaults
        assert env_var.required is False
        assert env_var.secret is False
        assert env_var.description is None
        assert env_var.default is None


class TestLifecycleConfig:
    """Tests for lifecycle commands configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.lifecycle_data = {
            "install": "./install.sh",
            "start": "docker compose up -d",
            "stop": "docker compose down",
            "logs": "docker compose logs",
            "status": "docker compose ps",
        }

    def test_lifecycle_config_full(self) -> None:
        """Verify full lifecycle config is valid."""
        # Given
        data = self.lifecycle_data

        # When
        lifecycle = LifecycleConfig.model_validate(data)

        # Then
        assert lifecycle.install == data["install"]
        assert lifecycle.start == data["start"]
        assert lifecycle.stop == data["stop"]
        assert lifecycle.logs == data["logs"]
        assert lifecycle.status == data["status"]

    def test_lifecycle_config_empty(self) -> None:
        """Verify empty lifecycle config uses defaults."""
        # Given
        data: dict[str, str] = {}

        # When
        lifecycle = LifecycleConfig.model_validate(data)

        # Then - all fields are None (defaults applied at runtime)
        assert lifecycle.install is None
        assert lifecycle.start is None
        assert lifecycle.stop is None


class TestMcpConfig:
    """Tests for MCP integration configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mcp_data = {
            "enabled": True,
            "type": "http-proxy",
            "endpoint": "http://localhost:8787/mcp",
        }

    def test_mcp_config_http_proxy(self) -> None:
        """Verify http-proxy MCP config is valid."""
        # Given
        data = self.mcp_data

        # When
        mcp = McpConfig.model_validate(data)

        # Then
        assert mcp.enabled == data["enabled"]
        assert mcp.type == data["type"]
        assert mcp.endpoint == data["endpoint"]

    def test_mcp_config_disabled(self) -> None:
        """Verify disabled MCP config."""
        # Given
        data = {"enabled": False}

        # When
        mcp = McpConfig.model_validate(data)

        # Then
        assert mcp.enabled is False



class TestPluginSchemaFull:
    """Tests for full plugin schema with all components."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.full_plugin_data = {
            "schema_version": "2026-01-22",
            "name": "OpenMemory",
            "description": "Persistent memory layer for AI agents",
            "service": {
                "type": "docker-compose",
                "compose_file": "docker-compose.yml",
            },
            "vendor": {
                "url": "https://github.com/CaviraOSS/OpenMemory.git",
                "ref": "v1.2.3",
            },
            "ports": [
                {
                    "name": "API",
                    "port": 8787,
                    "configurable": True,
                    "health_endpoint": "/health",
                },
                {
                    "name": "Dashboard",
                    "port": 3737,
                    "health_endpoint": "/",
                },
            ],
            "env_vars": [
                {
                    "name": "OPENAI_API_KEY",
                    "required": True,
                    "secret": True,
                    "description": "OpenAI API key for embeddings",
                },
            ],
            "lifecycle": {
                "install": "./install.sh",
                "start": "docker compose up -d",
                "stop": "docker compose down",
            },
            "mcp": {
                "enabled": True,
                "type": "http-proxy",
                "endpoint": "http://localhost:8787/mcp",
            },
        }

    def test_full_plugin_schema_is_valid(self) -> None:
        """Verify that a full plugin schema with all fields is valid."""
        # Given
        data = self.full_plugin_data

        # When
        plugin = PluginSchema.model_validate(data)

        # Then - basic fields
        assert plugin.schema_version == data["schema_version"]
        assert plugin.name == data["name"]
        assert plugin.description == data["description"]

        # And - service
        assert plugin.service is not None
        assert plugin.service.type == ServiceType.DOCKER_COMPOSE

        # And - vendor
        assert plugin.vendor is not None
        assert plugin.vendor.url == data["vendor"]["url"]

        # And - ports
        assert len(plugin.ports) == 2
        first_port = plugin.ports[0]
        assert first_port.name == "API"
        assert first_port.port == 8787

        # And - env_vars
        assert len(plugin.env_vars) == 1
        first_env = plugin.env_vars[0]
        assert first_env.name == "OPENAI_API_KEY"

        # And - lifecycle
        assert plugin.lifecycle is not None
        assert plugin.lifecycle.install == "./install.sh"

        # And - mcp
        assert plugin.mcp is not None
        assert plugin.mcp.enabled is True
