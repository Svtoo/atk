"""Manage ATK's section in Claude Code's user memory file (~/.claude/CLAUDE.md).

Claude Code reads ~/.claude/CLAUDE.md at session start. Lines of the form
    @/absolute/path/to/file.md
cause Claude Code to inline that file's content into its context.

ATK owns a delimited section within CLAUDE.md and keeps it populated with
@-references to each installed plugin's SKILL.md. The section is bounded by
HTML comment markers so ATK can locate and update it without touching anything
the user has written outside of it.
"""

from pathlib import Path

CLAUDE_MD_PATH = Path.home() / ".claude" / "CLAUDE.md"
ATK_SECTION_BEGIN = "<!-- ATK:BEGIN -->"
ATK_SECTION_END = "<!-- ATK:END -->"


def inject_skill_reference(skill_path: Path, claude_md_path: Path = CLAUDE_MD_PATH) -> bool:
    """Add an @-import reference to *skill_path* in the ATK section of CLAUDE.md.

    The reference is written as ``@/absolute/path/to/SKILL.md`` on its own line
    inside the ATK-managed section.

    Returns:
        True  -- the reference was added (file was modified).
        False -- the reference was already present (no-op, idempotent).

    Side effects:
        * Creates *claude_md_path* and its parent directory if they do not exist.
        * Creates the ATK section at the end of the file if it does not exist.
    """
    reference = f"@{skill_path.resolve()}"

    content = claude_md_path.read_text() if claude_md_path.exists() else ""

    begin_idx = content.find(ATK_SECTION_BEGIN)
    end_idx = content.find(ATK_SECTION_END)

    if begin_idx == -1 or end_idx == -1:
        # No ATK section yet -- append one.
        section = f"\n{ATK_SECTION_BEGIN}\n{reference}\n{ATK_SECTION_END}\n"
        new_content = content.rstrip("\n") + section
    else:
        # Extract lines inside the existing section.
        inner = content[begin_idx + len(ATK_SECTION_BEGIN) : end_idx]
        existing = {line.strip() for line in inner.splitlines() if line.strip()}

        if reference in existing:
            return False

        # Append reference just before the closing marker.
        new_inner = inner.rstrip("\n") + f"\n{reference}\n"
        new_content = (
            content[: begin_idx + len(ATK_SECTION_BEGIN)]
            + new_inner
            + content[end_idx:]
        )

    claude_md_path.parent.mkdir(parents=True, exist_ok=True)
    claude_md_path.write_text(new_content)
    return True


def remove_skill_reference(skill_path: Path, claude_md_path: Path = CLAUDE_MD_PATH) -> bool:
    """Remove the @-import reference to *skill_path* from the ATK section.

    Returns:
        True  -- the reference was removed.
        False -- the reference was not present (no-op).
    """
    if not claude_md_path.exists():
        return False

    reference = f"@{skill_path.resolve()}"
    content = claude_md_path.read_text()

    begin_idx = content.find(ATK_SECTION_BEGIN)
    end_idx = content.find(ATK_SECTION_END)

    if begin_idx == -1 or end_idx == -1:
        return False

    inner = content[begin_idx + len(ATK_SECTION_BEGIN) : end_idx]
    lines = [line for line in inner.splitlines(keepends=True) if line.strip() != reference]

    if len(lines) == len(inner.splitlines(keepends=True)):
        return False  # nothing was removed

    new_inner = "".join(lines)
    new_content = (
        content[: begin_idx + len(ATK_SECTION_BEGIN)]
        + new_inner
        + content[end_idx:]
    )
    claude_md_path.write_text(new_content)
    return True
