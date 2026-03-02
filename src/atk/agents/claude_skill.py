"""Claude Code skill injection via @-references in ~/.claude/CLAUDE.md.

Claude Code reads ~/.claude/CLAUDE.md at session start.  Lines of the form
    @/absolute/path/to/file.md
cause Claude Code to inline that file's content into its context.

ATK adds @-references inside its managed section so that each installed
plugin's SKILL.md is automatically available to Claude Code.
"""

from pathlib import Path

from atk.agents.managed_section import add_line, remove_line

CLAUDE_MD_PATH = Path.home() / ".claude" / "CLAUDE.md"


def inject_skill_reference(
    skill_path: Path, claude_md_path: Path = CLAUDE_MD_PATH
) -> bool:
    """Add an @-import reference to *skill_path* in the ATK section of CLAUDE.md.

    Returns True if the file was modified, False if the reference was already present.
    """
    reference = f"@{skill_path.resolve()}"
    return add_line(reference, claude_md_path)


def remove_skill_reference(
    skill_path: Path, claude_md_path: Path = CLAUDE_MD_PATH
) -> bool:
    """Remove the @-import reference to *skill_path* from the ATK section.

    Returns True if the reference was removed, False if it was not present.
    """
    reference = f"@{skill_path.resolve()}"
    return remove_line(reference, claude_md_path)

