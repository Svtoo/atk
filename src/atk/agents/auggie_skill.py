"""Auggie (Augment Code) skill injection via symlinks in ~/.augment/rules/.

Augment Code auto-loads every *.md file in ~/.augment/rules/ as global
instructions at session start.  ATK creates symlinks of the form

    ~/.augment/rules/atk-<plugin-name>.md  →  /installed/path/to/SKILL.md

so that each plugin's skill file is always read live (updates via
``atk upgrade`` are reflected automatically).
"""

from pathlib import Path

AUGMENT_RULES_DIR = Path.home() / ".augment" / "rules"


def inject_skill_symlink(
    plugin_name: str,
    skill_path: Path,
    rules_dir: Path = AUGMENT_RULES_DIR,
) -> bool:
    """Create a symlink ``atk-<plugin_name>.md → skill_path`` in *rules_dir*.

    Returns True if a symlink was created or updated, False if already correct.
    Raises FileExistsError if a regular file occupies the symlink path.
    """
    rules_dir.mkdir(parents=True, exist_ok=True)
    symlink = rules_dir / f"atk-{plugin_name}.md"
    target = skill_path.resolve()

    if symlink.is_symlink():
        if symlink.resolve() == target:
            return False
        symlink.unlink()
    elif symlink.exists():
        raise FileExistsError(
            f"{symlink} exists and is not a symlink managed by ATK"
        )

    symlink.symlink_to(target)
    return True


def remove_skill_symlink(
    plugin_name: str,
    rules_dir: Path = AUGMENT_RULES_DIR,
) -> bool:
    """Remove the ATK-managed symlink for *plugin_name*.

    Returns True if a symlink was removed, False if not present or is a regular file.
    """
    symlink = rules_dir / f"atk-{plugin_name}.md"
    if symlink.is_symlink():
        symlink.unlink()
        return True
    return False

