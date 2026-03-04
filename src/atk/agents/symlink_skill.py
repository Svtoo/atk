"""Generic skill symlink helpers shared by symlink-based agent skill modules.

All symlink-based agent integrations (Auggie, Gemini CLI) create an
ATK-managed symlink under an agent-specific directory.  This module
provides the common create/remove primitives so each agent module stays thin.
"""

from pathlib import Path


def create_skill_symlink(symlink: Path, target: Path) -> bool:
    """Create *symlink* → *target*, creating parent directories as needed.

    Returns True if a symlink was created or updated, False if already correct.
    Raises FileExistsError if a non-symlink occupies the symlink path.
    """
    symlink.parent.mkdir(parents=True, exist_ok=True)

    if symlink.is_symlink():
        if symlink.resolve() == target:
            return False
        symlink.unlink()
    elif symlink.exists():
        raise FileExistsError(
            f"{symlink} exists and is not a symlink managed by ATK"
        )

    symlink.symlink_to(target, target_is_directory=target.is_dir())
    return True


def remove_skill_symlink(symlink: Path) -> bool:
    """Remove *symlink* if it is an ATK-managed symlink.

    Returns True if removed, False if not present or not a symlink.
    """
    if symlink.is_symlink():
        symlink.unlink()
        return True
    return False

