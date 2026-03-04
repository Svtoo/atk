"""Gemini CLI skill injection via symlinks in ~/.gemini/skills/.

Gemini CLI auto-loads every subdirectory in ~/.gemini/skills/ that contains
a SKILL.md file. ATK creates symlinks of the form

    ~/.gemini/skills/atk-<plugin-name>  →  /installed/path/to/skill-dir/

so that each plugin's skill is always read live (updates via
``atk upgrade`` are reflected automatically).
"""

from pathlib import Path

from atk.agents.symlink_skill import create_skill_symlink
from atk.agents.symlink_skill import remove_skill_symlink as _remove_symlink

GEMINI_SKILLS_DIR = Path.home() / ".gemini" / "skills"


def skill_symlink_info(
    plugin_name: str,
    skill_path: Path,
    skills_dir: Path = GEMINI_SKILLS_DIR,
) -> tuple[Path, Path]:
    """Return ``(symlink_path, target_path)`` for display without creating anything.

    The target is the parent directory of *skill_path* because Gemini CLI
    expects skills to be self-contained directories.
    """
    return skills_dir / f"atk-{plugin_name}", skill_path.parent.resolve()


def inject_skill_symlink(
    plugin_name: str,
    skill_path: Path,
    skills_dir: Path = GEMINI_SKILLS_DIR,
) -> bool:
    """Create a symlink ``atk-<plugin_name> → skill_dir`` in *skills_dir*.

    The *skill_path* is the path to the SKILL.md file. We link its parent
    directory because Gemini CLI expects skills to be self-contained directories.

    Returns True if a symlink was created or updated, False if already correct.
    Raises FileExistsError if a regular file or directory occupies the symlink path.
    """
    symlink = skills_dir / f"atk-{plugin_name}"
    return create_skill_symlink(symlink, skill_path.parent.resolve())


def remove_skill_symlink(
    plugin_name: str,
    skills_dir: Path = GEMINI_SKILLS_DIR,
) -> bool:
    """Remove the ATK-managed symlink for *plugin_name*.

    Returns True if a symlink was removed, False if not present or is a regular file/dir.
    """
    return _remove_symlink(skills_dir / f"atk-{plugin_name}")
