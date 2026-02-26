"""Pure translation layer from McpConfig to agent-specific invocations."""

from dataclasses import dataclass

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

