"""Codex skill injection via read-directives in ~/.codex/AGENTS.md.

Codex has no native file-include syntax.  ATK manages an ATK-owned section
in ``~/.codex/AGENTS.md`` bounded by ``<!-- ATK:BEGIN -->`` /
``<!-- ATK:END -->`` markers and inserts a natural-language read directive:

    Read /absolute/path/to/SKILL.md for instructions on using the <name> MCP tools.

Codex is an agent with file-reading capability and follows this directive
at session start, loading the live file content.  The SKILL.md is never
copied — only its absolute path is stored, so plugin updates are reflected
automatically.
"""

from pathlib import Path

from atk.agents.managed_section import add_line, remove_line

CODEX_AGENTS_MD_PATH = Path.home() / ".codex" / "AGENTS.md"


def _build_directive(plugin_name: str, skill_path: Path) -> str:
    """Build the read-directive line for a plugin."""
    return f"Read {skill_path.resolve()} for instructions on using the {plugin_name} MCP tools."


def inject_skill_directive(
    plugin_name: str,
    skill_path: Path,
    agents_md_path: Path = CODEX_AGENTS_MD_PATH,
) -> bool:
    """Add a read-directive for *skill_path* in the ATK section of AGENTS.md.

    Returns True if the file was modified, False if the directive was already present.
    Creates the file, parent directories, and ATK section as needed.
    """
    directive = _build_directive(plugin_name, skill_path)
    return add_line(directive, agents_md_path)


def remove_skill_directive(
    plugin_name: str,
    skill_path: Path,
    agents_md_path: Path = CODEX_AGENTS_MD_PATH,
) -> bool:
    """Remove the read-directive for *skill_path* from the ATK section.

    Returns True if the directive was removed, False if it was not present.
    """
    directive = _build_directive(plugin_name, skill_path)
    return remove_line(directive, agents_md_path)

