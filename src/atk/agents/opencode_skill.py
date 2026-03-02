"""OpenCode skill injection via the ``instructions`` array in opencode.jsonc.

OpenCode natively resolves file paths in its ``instructions`` array and loads
their contents at session start.  ATK adds the absolute path of a plugin's
SKILL.md to this array so that OpenCode understands how to use the plugin's
MCP tools.

The config file lives at ``~/.config/opencode/opencode.jsonc``.
"""

import json
from pathlib import Path
from typing import Any

_DEFAULT_CONFIG_PATH = Path.home() / ".config" / "opencode" / "opencode.jsonc"


def _read_config(file_path: Path) -> dict[str, Any]:
    """Read and parse the OpenCode config file.

    Returns an empty dict if the file does not exist.

    Raises:
        ValueError: if the file exists but cannot be parsed as JSON.
    """
    if not file_path.exists():
        return {}
    try:
        return json.loads(file_path.read_text())  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Cannot parse {file_path.name} as JSON. "
            "If the file contains JSONC comments or trailing commas, "
            "remove them first or edit the entry manually."
        ) from exc


def _write_config(file_path: Path, data: dict[str, Any]) -> None:
    """Write the config dict back to disk, creating parent dirs as needed."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, indent=2) + "\n")


def inject_skill_instruction(
    skill_path: Path,
    config_path: Path = _DEFAULT_CONFIG_PATH,
) -> bool:
    """Add *skill_path* to the ``instructions`` array in opencode.jsonc.

    Returns True if the file was modified, False if the path was already present.
    Creates the file and parent directories as needed.
    """
    resolved = str(skill_path.resolve())
    data = _read_config(config_path)

    instructions: list[str] = data.get("instructions", [])
    if resolved in instructions:
        return False

    instructions.append(resolved)
    data["instructions"] = instructions
    _write_config(config_path, data)
    return True


def remove_skill_instruction(
    skill_path: Path,
    config_path: Path = _DEFAULT_CONFIG_PATH,
) -> bool:
    """Remove *skill_path* from the ``instructions`` array in opencode.jsonc.

    Returns True if the path was removed, False if it was not present.
    """
    resolved = str(skill_path.resolve())
    data = _read_config(config_path)

    instructions: list[str] = data.get("instructions", [])
    if resolved not in instructions:
        return False

    instructions.remove(resolved)
    data["instructions"] = instructions
    _write_config(config_path, data)
    return True


def remove_opencode_mcp_entry(
    plugin_name: str,
    config_path: Path = _DEFAULT_CONFIG_PATH,
) -> bool:
    """Remove the MCP entry for *plugin_name* from opencode.jsonc.

    Returns True if the entry was removed, False if it was not present.
    """
    data = _read_config(config_path)

    mcp: dict[str, Any] = data.get("mcp", {})
    if plugin_name not in mcp:
        return False

    del mcp[plugin_name]
    data["mcp"] = mcp
    _write_config(config_path, data)
    return True


def remove_opencode_plugin(
    plugin_name: str,
    skill_path: Path | None,
    config_path: Path = _DEFAULT_CONFIG_PATH,
) -> tuple[bool, bool]:
    """Remove both MCP entry and skill instruction in a single file write.

    Returns (mcp_removed, skill_removed).
    """
    data = _read_config(config_path)

    # Remove MCP entry
    mcp: dict[str, Any] = data.get("mcp", {})
    mcp_removed = plugin_name in mcp
    if mcp_removed:
        del mcp[plugin_name]
        data["mcp"] = mcp

    # Remove skill instruction
    skill_removed = False
    if skill_path is not None:
        resolved = str(skill_path.resolve())
        instructions: list[str] = data.get("instructions", [])
        if resolved in instructions:
            instructions.remove(resolved)
            data["instructions"] = instructions
            skill_removed = True

    if mcp_removed or skill_removed:
        _write_config(config_path, data)

    return mcp_removed, skill_removed

