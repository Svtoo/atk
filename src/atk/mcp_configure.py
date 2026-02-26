"""Orchestrate MCP agent configuration: invoke agent CLIs on the user's behalf.

This module contains the runner functions for each supported agent.  Each
function executes the agent's CLI subprocess and returns the exit code.
Displaying output, asking for confirmation, and reporting results are CLI
concerns and stay in cli.py.

As new agents are added (Codex, Auggie, OpenCode, …) their runner functions
belong here, alongside build_*_mcp_config() in mcp_agents.py.
"""

import subprocess

from atk.mcp_agents import AgentMcpConfig


def run_claude_mcp_add(config: AgentMcpConfig) -> int:
    """Invoke ``claude mcp add`` and return its exit code.

    Args:
        config: The agent config produced by ``build_claude_mcp_config()``.

    Returns:
        The exit code from the ``claude`` process (0 = success).

    Raises:
        FileNotFoundError: if ``claude`` is not found on PATH.
    """
    return subprocess.run(config.argv).returncode

