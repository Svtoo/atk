"""Tests for plugin YAML schema validation."""

import pytest
import yaml

from atk.plugin_schema import (
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
    """Tests for vendor configuration (name, url, docs)."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.vendor_name = "Mem0"
        self.vendor_url = "https://mem0.ai"
        self.vendor_docs = "https://docs.mem0.ai"
        self.vendor_data_full = {
            "name": self.vendor_name,
            "url": self.vendor_url,
            "docs": self.vendor_docs,
        }

    def test_vendor_config_with_all_fields(self) -> None:
        """Verify vendor config with all fields is valid."""
        # Given
        data = self.vendor_data_full

        # When
        vendor = VendorConfig.model_validate(data)

        # Then
        assert vendor.name == self.vendor_name
        assert vendor.url == self.vendor_url
        assert vendor.docs == self.vendor_docs

    def test_vendor_config_with_name_only(self) -> None:
        """Verify vendor config with only name is valid (url and docs are optional)."""
        # Given
        vendor_name = "Ollama"
        data = {"name": vendor_name}

        # When
        vendor = VendorConfig.model_validate(data)

        # Then
        assert vendor.name == vendor_name
        assert vendor.url is None
        assert vendor.docs is None

    def test_vendor_config_with_name_and_url(self) -> None:
        """Verify vendor config with name and url (no docs) is valid."""
        # Given
        vendor_name = "Ollama"
        vendor_url = "https://ollama.ai"
        data = {"name": vendor_name, "url": vendor_url}

        # When
        vendor = VendorConfig.model_validate(data)

        # Then
        assert vendor.name == vendor_name
        assert vendor.url == vendor_url
        assert vendor.docs is None

    def test_vendor_name_is_required(self) -> None:
        """Verify that vendor name is required."""
        # Given
        data = {"url": "https://example.com"}

        # When/Then
        with pytest.raises(ValueError, match="name"):
            VendorConfig.model_validate(data)


class TestPortConfig:
    """Tests for port configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.port_data = {
            "port": 8787,
            "protocol": "https",
            "description": "Main API endpoint",
        }

    def test_port_config_full(self) -> None:
        """Verify full port config is valid."""
        # Given
        port_number = 8787
        protocol = "https"
        description = "Main API endpoint"
        data = {"port": port_number, "protocol": protocol, "description": description}

        # When
        port = PortConfig.model_validate(data)

        # Then
        assert port.port == port_number
        assert port.protocol == protocol
        assert port.description == description

    def test_port_config_minimal(self) -> None:
        """Verify minimal port config with defaults."""
        # Given
        port_number = 8080
        data = {"port": port_number}

        # When
        port = PortConfig.model_validate(data)

        # Then
        assert port.port == port_number
        # And - defaults
        assert port.protocol == "http"
        assert port.description is None

    def test_port_is_required(self) -> None:
        """Verify that port is required."""
        # Given
        data = {"protocol": "https", "description": "Some endpoint"}

        # When/Then
        with pytest.raises(ValueError, match="port"):
            PortConfig.model_validate(data)


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
            "health_endpoint": "http://localhost:8080/health",
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
        assert lifecycle.health_endpoint == data["health_endpoint"]

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
        assert lifecycle.logs is None
        assert lifecycle.status is None
        assert lifecycle.health_endpoint is None


class TestMcpConfig:
    """Tests for MCP integration configuration."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.mcp_stdio_data = {
            "transport": "stdio",
            "command": "docker",
            "args": ["exec", "-i", "openmemory", "python", "-m", "mcp_server"],
            "env": ["PYTHONPATH"],
        }
        self.mcp_sse_data = {
            "transport": "sse",
            "endpoint": "http://localhost:8787/mcp",
        }

    def test_mcp_config_stdio_transport(self) -> None:
        """Verify stdio transport MCP config is valid."""
        # Given
        data = self.mcp_stdio_data

        # When
        mcp = McpConfig.model_validate(data)

        # Then
        assert mcp.transport == data["transport"]
        assert mcp.command == data["command"]
        assert mcp.args == data["args"]
        assert mcp.env == data["env"]
        assert mcp.endpoint is None

    def test_mcp_config_sse_transport(self) -> None:
        """Verify sse transport MCP config is valid."""
        # Given
        data = self.mcp_sse_data

        # When
        mcp = McpConfig.model_validate(data)

        # Then
        assert mcp.transport == data["transport"]
        assert mcp.endpoint == data["endpoint"]
        assert mcp.command is None
        assert mcp.args is None

    def test_mcp_config_stdio_minimal(self) -> None:
        """Verify minimal stdio config with only required fields."""
        # Given
        transport = "stdio"
        command = "python"
        data = {"transport": transport, "command": command}

        # When
        mcp = McpConfig.model_validate(data)

        # Then
        assert mcp.transport == transport
        assert mcp.command == command
        assert mcp.args is None
        assert mcp.env is None



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
                "name": "Cavira OSS",
                "url": "https://github.com/CaviraOSS/OpenMemory.git",
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
                "uninstall": "docker compose down -v",
                "start": "docker compose up -d",
                "stop": "docker compose down",
                "health_endpoint": "/health",
            },
            "mcp": {
                "transport": "sse",
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
        assert plugin.lifecycle.start == "docker compose up -d"
        assert plugin.lifecycle.stop == "docker compose down"
        assert plugin.lifecycle.health_endpoint == "/health"

        # And - mcp
        assert plugin.mcp is not None
        assert plugin.mcp.transport == "sse"
        assert plugin.mcp.endpoint == "http://localhost:8787/mcp"


class TestYamlParsing:
    """Tests for parsing full YAML plugin configurations from design doc examples."""

    def test_parse_docker_compose_service(self) -> None:
        """Parse openmemory example - Docker Compose service with MCP stdio."""
        import yaml

        # Given - exact YAML from docs/plugin-schema.md lines 271-309
        yaml_content = """
schema_version: "2026-01-22"
name: openmemory
description: "Persistent memory layer for AI agents"

vendor:
  name: "Mem0"
  url: "https://mem0.ai"
  docs: "https://docs.mem0.ai"

service:
  type: docker-compose
  compose_file: docker-compose.yml

ports:
  - port: 8765
    protocol: http
    description: "API endpoint"

env_vars:
  - name: OPENAI_API_KEY
    description: "OpenAI API key for embeddings"
    required: true
    secret: true

mcp:
  transport: stdio
  command: docker
  args:
    - exec
    - -i
    - langfuse
    - npx
    - "@langfuse/mcp-server"
  env:
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
"""
        # When
        data = yaml.safe_load(yaml_content)
        plugin = PluginSchema.model_validate(data)

        # Then - core fields
        assert plugin.schema_version == "2026-01-22"
        assert plugin.name == "openmemory"
        assert plugin.description == "Persistent memory layer for AI agents"

        # Then - vendor
        assert plugin.vendor is not None
        assert plugin.vendor.name == "Mem0"
        assert plugin.vendor.url == "https://mem0.ai"
        assert plugin.vendor.docs == "https://docs.mem0.ai"

        # Then - service
        assert plugin.service is not None
        assert plugin.service.type == ServiceType.DOCKER_COMPOSE
        assert plugin.service.compose_file == "docker-compose.yml"

        # Then - ports
        assert len(plugin.ports) == 1
        port = plugin.ports[0]
        assert port.port == 8765
        assert port.protocol == "http"
        assert port.description == "API endpoint"

        # Then - env_vars
        assert len(plugin.env_vars) == 1
        env_var = plugin.env_vars[0]
        assert env_var.name == "OPENAI_API_KEY"
        assert env_var.description == "OpenAI API key for embeddings"
        assert env_var.required is True
        assert env_var.secret is True

        # Then - mcp
        assert plugin.mcp is not None
        assert plugin.mcp.transport == "stdio"
        assert plugin.mcp.command == "docker"
        assert plugin.mcp.args == ["exec", "-i", "langfuse", "npx", "@langfuse/mcp-server"]
        assert plugin.mcp.env == ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]


class TestLifecycleValidation:
    """Tests for lifecycle validation rules."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.base_plugin_data = {
            "schema_version": "2026-01-23",
            "name": "test-plugin",
            "description": "A test plugin",
        }

    def test_install_without_uninstall_is_invalid(self) -> None:
        """Verify that defining install without uninstall raises validation error."""
        # Given - plugin with install but no uninstall
        plugin_data = self.base_plugin_data.copy()
        plugin_data["lifecycle"] = {"install": "./install.sh"}

        # When/Then - validation should fail
        with pytest.raises(ValueError, match="uninstall.*required.*install"):
            PluginSchema.model_validate(plugin_data)

    def test_uninstall_without_install_is_valid(self) -> None:
        """Verify that defining uninstall without install is allowed."""
        # Given - plugin with uninstall but no install
        plugin_data = self.base_plugin_data.copy()
        plugin_data["lifecycle"] = {"uninstall": "./uninstall.sh"}

        # When
        plugin = PluginSchema.model_validate(plugin_data)

        # Then - validation succeeds
        assert plugin.lifecycle is not None
        assert plugin.lifecycle.uninstall == "./uninstall.sh"
        assert plugin.lifecycle.install is None

    def test_install_with_uninstall_is_valid(self) -> None:
        """Verify that defining both install and uninstall is valid."""
        # Given - plugin with both install and uninstall
        install_cmd = "./install.sh"
        uninstall_cmd = "./uninstall.sh"
        plugin_data = self.base_plugin_data.copy()
        plugin_data["lifecycle"] = {"install": install_cmd, "uninstall": uninstall_cmd}

        # When
        plugin = PluginSchema.model_validate(plugin_data)

        # Then - validation succeeds
        assert plugin.lifecycle is not None
        assert plugin.lifecycle.install == install_cmd
        assert plugin.lifecycle.uninstall == uninstall_cmd

    def test_neither_install_nor_uninstall_is_valid(self) -> None:
        """Verify that having neither install nor uninstall is valid."""
        # Given - plugin with lifecycle but no install or uninstall
        plugin_data = self.base_plugin_data.copy()
        plugin_data["lifecycle"] = {"start": "docker compose up -d", "stop": "docker compose down"}

        # When
        plugin = PluginSchema.model_validate(plugin_data)

        # Then - validation succeeds
        assert plugin.lifecycle is not None
        assert plugin.lifecycle.install is None
        assert plugin.lifecycle.uninstall is None
        assert plugin.lifecycle.start == "docker compose up -d"

    def test_parse_systemd_service(self) -> None:
        """Parse ollama example - Systemd service with install lifecycle."""
        # Given - exact YAML from docs/plugin-schema.md lines 328-348
        yaml_content = """
schema_version: "2026-01-22"
name: ollama
description: "Local LLM server"

vendor:
  name: "Ollama"
  url: "https://ollama.ai"

service:
  type: systemd
  unit_name: ollama

ports:
  - port: 11434
    protocol: http
    description: "Ollama API"

lifecycle:
  install: "curl -fsSL https://ollama.ai/install.sh | sh"
  uninstall: "systemctl stop ollama && systemctl disable ollama"
"""
        # When
        data = yaml.safe_load(yaml_content)
        plugin = PluginSchema.model_validate(data)

        # Then - core fields
        assert plugin.schema_version == "2026-01-22"
        assert plugin.name == "ollama"
        assert plugin.description == "Local LLM server"

        # Then - vendor
        assert plugin.vendor is not None
        assert plugin.vendor.name == "Ollama"
        assert plugin.vendor.url == "https://ollama.ai"

        # Then - service
        assert plugin.service is not None
        assert plugin.service.type == ServiceType.SYSTEMD
        assert plugin.service.unit_name == "ollama"

        # Then - ports
        assert len(plugin.ports) == 1
        port = plugin.ports[0]
        assert port.port == 11434
        assert port.protocol == "http"
        assert port.description == "Ollama API"

        # Then - lifecycle
        assert plugin.lifecycle is not None
        assert plugin.lifecycle.install == "curl -fsSL https://ollama.ai/install.sh | sh"

    def test_parse_script_service(self) -> None:
        """Parse custom-tool example - Script service with full lifecycle."""
        # Given - exact YAML from docs/plugin-schema.md lines 352-366
        yaml_content = """
schema_version: "2026-01-22"
name: custom-tool
description: "Custom development tool"

service:
  type: script

lifecycle:
  start: "./start.sh"
  stop: "pkill -f custom-tool"
  status: "pgrep -f custom-tool > /dev/null"
  logs: "tail -f logs/custom-tool.log"
  install: "./install.sh"
  uninstall: "./uninstall.sh"
"""
        # When
        data = yaml.safe_load(yaml_content)
        plugin = PluginSchema.model_validate(data)

        # Then - core fields
        assert plugin.schema_version == "2026-01-22"
        assert plugin.name == "custom-tool"
        assert plugin.description == "Custom development tool"

        # Then - service
        assert plugin.service is not None
        assert plugin.service.type == ServiceType.SCRIPT

        # Then - lifecycle
        assert plugin.lifecycle is not None
        assert plugin.lifecycle.start == "./start.sh"
        assert plugin.lifecycle.stop == "pkill -f custom-tool"
        assert plugin.lifecycle.status == "pgrep -f custom-tool > /dev/null"
        assert plugin.lifecycle.logs == "tail -f logs/custom-tool.log"
        assert plugin.lifecycle.install == "./install.sh"

        # Then - no vendor, ports, env_vars, or mcp (minimal config)
        assert plugin.vendor is None
        assert plugin.ports == []
        assert plugin.env_vars == []
        assert plugin.mcp is None
