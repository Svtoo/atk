"""Manage ATK-owned sections in text files.

ATK delimits its content with HTML comment markers:

    <!-- ATK:BEGIN -->
    ... ATK-managed lines ...
    <!-- ATK:END -->

This module provides add_line/remove_line to manipulate individual lines
within that section, creating the section and parent directories as needed.
"""

from pathlib import Path

ATK_SECTION_BEGIN = "<!-- ATK:BEGIN -->"
ATK_SECTION_END = "<!-- ATK:END -->"


def add_line(line: str, file_path: Path) -> bool:
    """Add *line* to the ATK section in *file_path*.

    Returns True if the file was modified, False if *line* was already present.
    Creates the file, parent directories, and ATK section as needed.
    """
    content = file_path.read_text() if file_path.exists() else ""

    begin_idx = content.find(ATK_SECTION_BEGIN)
    end_idx = content.find(ATK_SECTION_END)

    if begin_idx == -1 or end_idx == -1:
        # No ATK section yet -- append one.
        section = f"\n{ATK_SECTION_BEGIN}\n{line}\n{ATK_SECTION_END}\n"
        new_content = content.rstrip("\n") + section
    else:
        # Extract lines inside the existing section.
        inner = content[begin_idx + len(ATK_SECTION_BEGIN) : end_idx]
        existing = {entry.strip() for entry in inner.splitlines() if entry.strip()}

        if line in existing:
            return False

        # Append line just before the closing marker.
        new_inner = inner.rstrip("\n") + f"\n{line}\n"
        new_content = (
            content[: begin_idx + len(ATK_SECTION_BEGIN)]
            + new_inner
            + content[end_idx:]
        )

    file_path.parent.mkdir(parents=True, exist_ok=True)
    # Remove broken symlinks so write_text doesn't follow them to a
    # non-existent target (e.g. ~/.codex/AGENTS.md → missing path).
    if file_path.is_symlink() and not file_path.exists():
        file_path.unlink()
    file_path.write_text(new_content)
    return True


def remove_line(line: str, file_path: Path) -> bool:
    """Remove *line* from the ATK section in *file_path*.

    Returns True if the line was removed, False if it was not present.
    """
    if not file_path.exists():
        return False

    content = file_path.read_text()

    begin_idx = content.find(ATK_SECTION_BEGIN)
    end_idx = content.find(ATK_SECTION_END)

    if begin_idx == -1 or end_idx == -1:
        return False

    inner = content[begin_idx + len(ATK_SECTION_BEGIN) : end_idx]
    lines = [entry for entry in inner.splitlines(keepends=True) if entry.strip() != line]

    if len(lines) == len(inner.splitlines(keepends=True)):
        return False  # nothing was removed

    new_inner = "".join(lines)
    new_content = (
        content[: begin_idx + len(ATK_SECTION_BEGIN)]
        + new_inner
        + content[end_idx:]
    )
    file_path.write_text(new_content)
    return True

