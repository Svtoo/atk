"""MCP (Model Context Protocol) configuration generation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atk.env import load_env_file
from atk.plugin_schema import PluginSchema

# Environment variable name for plugin directory
ATK_PLUGIN_DIR = "ATK_PLUGIN_DIR"

@dataclass
class McpConfigResult:
    """Result of generating MCP config."""

    plugin_name: str
    config: dict[str, Any]
    missing_vars: list[str]


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
) -> McpConfigResult:
    """Generate MCP config dict for a plugin.

    Substitutes $ATK_PLUGIN_DIR and ${ATK_PLUGIN_DIR} in command, args, and
    working_dir with the absolute path to the plugin directory.

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
            config["command"] = substitute_plugin_dir(mcp.command, plugin_dir)
        if mcp.args:
            config["args"] = [substitute_plugin_dir(arg, plugin_dir) for arg in mcp.args]
        if mcp.working_dir:
            config["cwd"] = substitute_plugin_dir(mcp.working_dir, plugin_dir)
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

