"""Pure translation layer from McpConfig to agent-specific invocations."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from atk.mcp import NOT_SET, McpConfig, SseMcpConfig, StdioMcpConfig


@dataclass
class AgentMcpConfig:
    """Configuration produced by an agent builder function.

    Holds all information needed to invoke the agent's MCP registration
    command.  The argv list is suitable for passing directly to subprocess.run().
    Additional fields can be added here as the multi-agent feature evolves
    without changing the builder function signatures.
    """

    argv: list[str]


def build_claude_mcp_config(config: McpConfig, scope: str = "user") -> AgentMcpConfig:
    """Build the agent config for `claude mcp add` from an McpConfig.

    Environment variables whose value is NOT_SET are omitted — claude is
    invoked with only the variables that have resolved values.

    Args:
        config: The resolved MCP config from generate_mcp_config().
        scope:  Claude scope ('user' or 'local'). Defaults to 'user'.

    Returns:
        AgentMcpConfig with the full argv for subprocess.run().
    """
    argv: list[str] = ["claude", "mcp", "add"]

    if isinstance(config, SseMcpConfig):
        argv += ["--transport", "sse"]

    argv += ["--scope", scope]

    # One -e KEY=VAL per resolved variable; skip unset ones.
    for key, val in config.env.items():
        if val != NOT_SET:
            argv += ["-e", f"{key}={val}"]

    # "--" terminates claude's option parsing so that server args like
    # "--directory /path" are not misinterpreted as claude mcp add options.
    argv.append("--")
    argv.append(config.identifier)

    if isinstance(config, SseMcpConfig):
        argv.append(config.url)
    elif isinstance(config, StdioMcpConfig):
        argv.append(config.command)
        argv.extend(config.args)

    return AgentMcpConfig(argv=argv)


def build_codex_mcp_config(config: McpConfig) -> AgentMcpConfig:
    """Build the agent config for ``codex mcp add`` from an McpConfig.

    For stdio: ``codex mcp add [--env K=V ...] <name> -- <cmd> [args...]``
    For SSE:   ``codex mcp add [--env K=V ...] <name> --url <url>``

    Env vars with NOT_SET values are omitted. The ``--`` separator before the
    command is required by Codex's CLI parser so that server args like
    ``--directory /path`` are not treated as codex options.
    """
    argv: list[str] = ["codex", "mcp", "add"]

    for key, val in config.env.items():
        if val != NOT_SET:
            argv += ["--env", f"{key}={val}"]

    argv.append(config.identifier)

    if isinstance(config, SseMcpConfig):
        argv += ["--url", config.url]
    elif isinstance(config, StdioMcpConfig):
        argv += ["--", config.command, *config.args]

    return AgentMcpConfig(argv=argv)


def build_auggie_mcp_config(config: McpConfig) -> AgentMcpConfig:
    """Build the agent config for ``auggie mcp add-json`` from an McpConfig.

    Auggie's ``add-json`` subcommand accepts a single-line JSON string.
    For stdio: ``{"command": "...", "args": [...], "env": {...}}``
    For SSE:   ``{"type": "sse", "url": "..."}``

    Args must be a JSON array — auggie silently drops all mcpServers entries
    if any entry has args as a string instead of an array.
    Env vars with NOT_SET values are omitted.
    """
    payload: dict[str, Any]

    if isinstance(config, SseMcpConfig):
        payload = {"type": "sse", "url": config.url}
    else:
        assert isinstance(config, StdioMcpConfig)
        resolved_env = {k: v for k, v in config.env.items() if v != NOT_SET}
        payload = {
            "command": config.command,
            "args": config.args,
            "env": resolved_env,
        }

    json_str = json.dumps(payload, separators=(",", ":"))
    return AgentMcpConfig(argv=["auggie", "mcp", "add-json", config.identifier, json_str])


def _default_opencode_config_dir() -> Path:
    """Return the default global OpenCode config directory.

    OpenCode's global config lives at ``~/.config/opencode/`` on all platforms.
    This is consistent with the XDG base-dir convention that OpenCode follows
    (documented at https://opencode.ai/docs/config/).
    """
    return Path.home() / ".config" / "opencode"


@dataclass
class OpenCodeMcpConfig:
    """Configuration for writing an MCP entry to opencode.jsonc.

    OpenCode's ``mcp add`` is an interactive TUI and cannot be scripted.
    ATK writes directly to the global opencode.jsonc config file instead.
    """

    entry_key: str
    entry_value: dict[str, Any]
    file_path: Path


def build_opencode_mcp_config(
    config: McpConfig,
    config_dir: Path | None = None,
) -> OpenCodeMcpConfig:
    """Build the OpenCode MCP config from an McpConfig.

    OpenCode uses ``type: "local"`` for stdio and ``type: "remote"`` for SSE.
    The ``command`` field is a full array (executable + args).
    Env vars use the key ``environment`` (not ``env``).
    Env vars with NOT_SET values are omitted.

    Args:
        config:     The resolved MCP config from generate_mcp_config().
        config_dir: Directory where opencode.jsonc will be written.
                    Defaults to ``~/.config/opencode/`` (the global OpenCode
                    config directory).  Pass an explicit path in tests.

    Returns:
        OpenCodeMcpConfig ready for run_opencode_mcp_add().
    """
    effective_dir = config_dir if config_dir is not None else _default_opencode_config_dir()
    entry_value: dict[str, Any]

    if isinstance(config, SseMcpConfig):
        entry_value = {"type": "remote", "url": config.url, "enabled": True}
    else:
        assert isinstance(config, StdioMcpConfig)
        resolved_env = {k: v for k, v in config.env.items() if v != NOT_SET}
        entry_value = {
            "type": "local",
            "command": [config.command, *config.args],
            "environment": resolved_env,
            "enabled": True,
        }

    return OpenCodeMcpConfig(
        entry_key=config.identifier,
        entry_value=entry_value,
        file_path=effective_dir / "opencode.jsonc",
    )

