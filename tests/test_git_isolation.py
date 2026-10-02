"""Tests that the suite's git commands stay inside their own temp directories."""

import os
import subprocess
import sys
from pathlib import Path

from tests.conftest import git_commit_all

REPO_ROOT = Path(__file__).parent.parent
CHILD_TEST = """
from atk.init import init_atk_home


def test_init(tmp_path):
    init_atk_home(tmp_path / ".atk")
"""


def _repository_state(repo: Path) -> tuple[str, bytes, str]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout
    bare = subprocess.run(
        ["git", "config", "core.bare"], cwd=repo, check=True, capture_output=True, text=True,
    ).stdout
    return head, (repo / ".git" / "index").read_bytes(), bare


def test_suite_keeps_git_inside_test_dirs_when_hook_variables_are_inherited(
    tmp_path: Path,
) -> None:
    # Given - the variables git exports to a pre-commit hook in a linked worktree
    hook_repo = tmp_path / "hook-repo"
    hook_repo.mkdir()
    subprocess.run(["git", "init"], cwd=hook_repo, check=True, capture_output=True)
    (hook_repo / "README.md").write_text("hook repo\n")
    git_commit_all(hook_repo, "Initial commit")
    state_before = _repository_state(hook_repo)
    child_test = tmp_path / "child" / "test_child.py"
    child_test.parent.mkdir()
    child_test.write_text(CHILD_TEST)
    hook_env = {
        **os.environ,
        "GIT_DIR": str(hook_repo / ".git"),
        "GIT_INDEX_FILE": str(hook_repo / ".git" / "index"),
    }

    # When
    result = subprocess.run(
        [
            sys.executable, "-m", "pytest", str(child_test),
            "-p", "tests.conftest", "-p", "no:cacheprovider", "-q",
            "--rootdir", str(child_test.parent),
        ],
        cwd=REPO_ROOT, env=hook_env, capture_output=True, text=True,
    )

    # Then
    assert result.returncode == 0, result.stdout
    assert _repository_state(hook_repo) == state_before
