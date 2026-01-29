"""MCP (Model Context Protocol) configuration generation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atk.env import load_env_file
from atk.plugin_schema import PluginSchema


@dataclass
class McpConfigResult:
    """Result of generating MCP config."""

    plugin_name: str
    config: dict[str, Any]
    missing_vars: list[str]


def generate_mcp_config(
    plugin: PluginSchema,
    plugin_dir: Path,
    plugin_identifier: str,
) -> McpConfigResult:
    """Generate MCP config dict for a plugin.

    Args:
        plugin: The plugin schema.
        plugin_dir: Path to the plugin directory.
        plugin_identifier: The identifier to use as the key in the output.

    Returns:
        McpConfigResult with the config dict and list of missing env vars.
    """
    if plugin.mcp is None:
        raise ValueError(f"Plugin '{plugin.name}' has no MCP configuration")

    mcp = plugin.mcp
    env_file = plugin_dir / ".env"
    env_values = load_env_file(env_file) if env_file.exists() else {}

    config: dict[str, Any] = {}
    missing_vars: list[str] = []

    if mcp.transport == "stdio":
        if mcp.command:
            config["command"] = mcp.command
        if mcp.args:
            config["args"] = mcp.args
    elif mcp.transport == "sse":
        if mcp.endpoint:
            config["url"] = mcp.endpoint

    if mcp.env:
        env_dict: dict[str, str] = {}
        for var_name in mcp.env:
            value = env_values.get(var_name)
            if value:
                env_dict[var_name] = value
            else:
                env_dict[var_name] = "<NOT_SET>"
                missing_vars.append(var_name)
        if env_dict:
            config["env"] = env_dict

    return McpConfigResult(
        plugin_name=plugin.name,
        config={plugin_identifier: config},
        missing_vars=missing_vars,
    )

