"""`atk doctor` — repair an ATK Home's .gitignore and untrack leaked secrets.

Historical bug: per-plugin `!plugins/<name>/**` exemptions were appended AFTER
the `*.env` rule. Because .gitignore is last-match-wins, those exemptions
re-included plugin .env files, which `atk add`'s auto-commit then committed.

This migration re-orders the secret rules last (idempotent) and untracks any
secret files that already slipped into the repo. It does NOT rotate keys or
rewrite history — both are surfaced to the user as follow-ups.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from atk.git import (
    git_add,
    git_commit,
    git_push,
    git_rm_cached,
    list_tracked_secrets,
    normalize_gitignore,
)


@dataclass
class DoctorResult:
    """Outcome of a doctor run, for the CLI to report."""

    gitignore_fixed: bool
    untracked_secrets: list[str] = field(default_factory=list)
    committed: bool = False


def run_doctor(
    atk_home: Path,
    *,
    auto_commit: bool,
    auto_push: bool = False,
) -> DoctorResult:
    """Repair the ATK Home .gitignore and untrack any committed secret files.

    Order matters: normalise the .gitignore FIRST so the secret files become
    ignored, THEN `git rm --cached` them — that way the subsequent stage can't
    re-add a now-ignored file. Commits the repair when auto_commit is on,
    mirroring the add/remove commands.

    Args:
        atk_home: Path to the (initialized) ATK Home directory.
        auto_commit: Whether to commit the repair (from manifest config).
        auto_push: Whether to push after committing (subordinate to commit).

    Returns:
        DoctorResult describing what changed.
    """
    gitignore_fixed = normalize_gitignore(atk_home)

    tracked_secrets = list_tracked_secrets(atk_home)
    if tracked_secrets:
        git_rm_cached(atk_home, tracked_secrets)
    if gitignore_fixed:
        git_add(atk_home, [".gitignore"])

    committed = False
    if (gitignore_fixed or tracked_secrets) and auto_commit:
        committed = git_commit(atk_home, "atk doctor: keep secrets out of git")
        if committed and auto_push:
            git_push(atk_home)

    return DoctorResult(
        gitignore_fixed=gitignore_fixed,
        untracked_secrets=tracked_secrets,
        committed=committed,
    )
