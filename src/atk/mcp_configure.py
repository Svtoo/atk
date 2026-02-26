"""Orchestrate MCP agent configuration: invoke agent CLIs on the user's behalf.

Each function executes the agent's CLI subprocess (or writes a config file)
and returns the exit code.  Displaying output, asking for confirmation, and
reporting results are CLI concerns and stay in cli.py.
"""

import json
import subprocess
from typing import Any

from atk.mcp_agents import AgentMcpConfig, OpenCodeMcpConfig


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


def run_codex_mcp_add(config: AgentMcpConfig) -> int:
    """Invoke ``codex mcp add`` and return its exit code.

    Args:
        config: The agent config produced by ``build_codex_mcp_config()``.

    Returns:
        The exit code from the ``codex`` process (0 = success).

    Raises:
        FileNotFoundError: if ``codex`` is not found on PATH.
    """
    return subprocess.run(config.argv).returncode


def run_auggie_mcp_add(config: AgentMcpConfig) -> int:
    """Invoke ``auggie mcp add-json`` and return its exit code.

    Args:
        config: The agent config produced by ``build_auggie_mcp_config()``.

    Returns:
        The exit code from the ``auggie`` process (0 = success).

    Raises:
        FileNotFoundError: if ``auggie`` is not found on PATH.
    """
    return subprocess.run(config.argv).returncode


def run_opencode_mcp_add(config: OpenCodeMcpConfig) -> int:
    """Write an MCP entry to opencode.jsonc and return 0 on success.

    Creates the file if it does not exist.  If the file already exists,
    reads it as JSON and merges the new entry under the ``mcp`` key.

    The file is written as clean JSON (valid JSONC).  If the existing file
    contains JSONC-specific syntax (comments, trailing commas) that stdlib
    json cannot parse, raises ValueError with a clear message.

    Args:
        config: The config produced by ``build_opencode_mcp_config()``.

    Returns:
        0 always (errors are surfaced via exceptions).

    Raises:
        ValueError: if the existing file cannot be parsed as JSON.
        OSError:    if the file cannot be read or written.
    """
    file_path = config.file_path
    data: dict[str, Any]

    if file_path.exists():
        try:
            data = json.loads(file_path.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Cannot parse {file_path.name} as JSON. "
                "If the file contains JSONC comments or trailing commas, "
                "remove them first or add the entry manually."
            ) from exc
    else:
        data = {}

    if "mcp" not in data:
        data["mcp"] = {}

    data["mcp"][config.entry_key] = config.entry_value
    file_path.write_text(json.dumps(data, indent=2) + "\n")
    return 0

