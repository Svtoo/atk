"""MCP (Model Context Protocol) configuration generation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atk.env import load_env_file
from atk.plugin_schema import PluginSchema

# Environment variable name for plugin directory
ATK_PLUGIN_DIR = "ATK_PLUGIN_DIR"

# Sentinel written into env when a variable has no resolved value.
# Single authoritative definition — import from here everywhere else.
NOT_SET = "<NOT_SET>"


@dataclass
class McpConfig(ABC):
    """Resolved MCP server configuration for a plugin.

    Produced by generate_mcp_config() after substituting environment variables
    and $ATK_PLUGIN_DIR placeholders.  Use StdioMcpConfig or SseMcpConfig
    directly; this base class is never instantiated on its own.
    """

    identifier: str       # Key used in MCP JSON output and agent CLI commands
    plugin_name: str      # Display name from the plugin schema
    env: dict[str, str]   # Resolved env vars; NOT_SET sentinel for missing ones
    missing_vars: list[str]  # Names of variables that could not be resolved

    @abstractmethod
    def to_mcp_dict(self) -> dict[str, Any]:
        """Serialize to the standard MCP JSON config structure.

        The returned dict has the identifier as the single top-level key,
        matching what MCP clients expect in their configuration files.
        """


@dataclass
class StdioMcpConfig(McpConfig):
    """Resolved MCP config for a stdio (command-based) server."""

    command: str
    args: list[str]

    def to_mcp_dict(self) -> dict[str, Any]:
        inner: dict[str, Any] = {"command": self.command}
        if self.args:
            inner["args"] = self.args
        if self.env:
            inner["env"] = self.env
        return {self.identifier: inner}


@dataclass
class SseMcpConfig(McpConfig):
    """Resolved MCP config for an SSE (URL-based) server."""

    url: str

    def to_mcp_dict(self) -> dict[str, Any]:
        inner: dict[str, Any] = {"url": self.url}
        if self.env:
            inner["env"] = self.env
        return {self.identifier: inner}


def substitute_plugin_dir(value: str, plugin_dir: Path) -> str:
    """Substitute $ATK_PLUGIN_DIR and ${ATK_PLUGIN_DIR} with absolute path.

    Args:
        value: String that may contain $ATK_PLUGIN_DIR or ${ATK_PLUGIN_DIR}.
        plugin_dir: Absolute path to the plugin directory.

    Returns:
        String with substitutions applied.
    """
    plugin_dir_str = str(plugin_dir.resolve())
    # Replace ${ATK_PLUGIN_DIR} first (more specific)
    value = value.replace(f"${{{ATK_PLUGIN_DIR}}}", plugin_dir_str)
    # Then replace $ATK_PLUGIN_DIR
    value = value.replace(f"${ATK_PLUGIN_DIR}", plugin_dir_str)
    return value


def generate_mcp_config(
    plugin: PluginSchema,
    plugin_dir: Path,
    plugin_identifier: str,
) -> McpConfig:
    """Resolve and return the MCP config for a plugin.

    Substitutes $ATK_PLUGIN_DIR and ${ATK_PLUGIN_DIR} in command and args.
    Resolves environment variables from the plugin's .env file and declared
    defaults; marks unresolvable variables with NOT_SET.

    Args:
        plugin: The plugin schema.
        plugin_dir: Path to the plugin directory.
        plugin_identifier: The identifier used as the key in MCP JSON output.

    Returns:
        StdioMcpConfig for stdio transport, SseMcpConfig for SSE transport.
    """
    if plugin.mcp is None:
        raise ValueError(f"Plugin '{plugin.name}' has no MCP configuration")

    mcp = plugin.mcp
    env_file = plugin_dir / ".env"
    env_values = load_env_file(env_file) if env_file.exists() else {}

    env: dict[str, str] = {}
    missing_vars: list[str] = []
    if mcp.env:
        env_var_defaults = {ev.name: ev.default for ev in plugin.env_vars if ev.default is not None}
        for var_name in mcp.env:
            value = env_values.get(var_name) or env_var_defaults.get(var_name)
            if value:
                env[var_name] = value
            else:
                env[var_name] = NOT_SET
                missing_vars.append(var_name)

    if mcp.transport == "stdio":
        if not mcp.command:
            raise ValueError(
                f"Plugin '{plugin.name}' has transport 'stdio' but no command defined."
            )
        return StdioMcpConfig(
            identifier=plugin_identifier,
            plugin_name=plugin.name,
            command=substitute_plugin_dir(mcp.command, plugin_dir),
            args=[substitute_plugin_dir(a, plugin_dir) for a in (mcp.args or [])],
            env=env,
            missing_vars=missing_vars,
        )

    # sse
    if not mcp.endpoint:
        raise ValueError(
            f"Plugin '{plugin.name}' has transport 'sse' but no endpoint defined."
        )
    return SseMcpConfig(
        identifier=plugin_identifier,
        plugin_name=plugin.name,
        url=mcp.endpoint,
        env=env,
        missing_vars=missing_vars,
    )


def format_mcp_plaintext(config: McpConfig) -> str:
    """Format MCP config as human-readable plaintext with Rich markup.

    Renders sections appropriate to the transport type:
    - StdioMcpConfig: Name, Command (command + args joined), Environment Variables
    - SseMcpConfig:   Name, URL, Environment Variables

    Args:
        config: The resolved MCP config.

    Returns:
        A string containing Rich markup ready for console.print().
    """
    lines: list[str] = []

    lines.append(f"[bold]Name:[/bold]    {config.plugin_name}")

    if isinstance(config, StdioMcpConfig):
        command_parts = [config.command, *config.args]
        lines.append(f"[bold]Command:[/bold]  {' '.join(command_parts)}")
    elif isinstance(config, SseMcpConfig):
        lines.append(f"[bold]URL:[/bold]     {config.url}")

    if config.env:
        lines.append("")
        lines.append("[bold]Environment Variables:[/bold]")
        for key, val in config.env.items():
            if val == NOT_SET:
                lines.append(f"  {key}=[red]{val}[/red]")
            else:
                lines.append(f"  {key}=[dim]{val}[/dim]")

    return "\n".join(lines)

