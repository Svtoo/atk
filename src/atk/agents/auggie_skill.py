"""Auggie (Augment Code) skill injection via symlinks in ~/.augment/rules/.

Augment Code auto-loads every *.md file in ~/.augment/rules/ as global
instructions at session start.  ATK creates symlinks of the form

    ~/.augment/rules/atk-<plugin-name>.md  →  /installed/path/to/SKILL.md

so that each plugin's skill file is always read live (updates via
``atk upgrade`` are reflected automatically).
"""

from pathlib import Path

from atk.agents.symlink_skill import create_skill_symlink
from atk.agents.symlink_skill import remove_skill_symlink as _remove_symlink

AUGMENT_RULES_DIR = Path.home() / ".augment" / "rules"


def skill_symlink_info(
    plugin_name: str,
    skill_path: Path,
    rules_dir: Path = AUGMENT_RULES_DIR,
) -> tuple[Path, Path]:
    """Return ``(symlink_path, target_path)`` for display without creating anything."""
    return rules_dir / f"atk-{plugin_name}.md", skill_path.resolve()


def inject_skill_symlink(
    plugin_name: str,
    skill_path: Path,
    rules_dir: Path = AUGMENT_RULES_DIR,
) -> bool:
    """Create a symlink ``atk-<plugin_name>.md → skill_path`` in *rules_dir*.

    Returns True if a symlink was created or updated, False if already correct.
    Raises FileExistsError if a regular file occupies the symlink path.
    """
    symlink = rules_dir / f"atk-{plugin_name}.md"
    return create_skill_symlink(symlink, skill_path.resolve())


def remove_skill_symlink(
    plugin_name: str,
    rules_dir: Path = AUGMENT_RULES_DIR,
) -> bool:
    """Remove the ATK-managed symlink for *plugin_name*.

    Returns True if a symlink was removed, False if not present or is a regular file.
    """
    return _remove_symlink(rules_dir / f"atk-{plugin_name}.md")

