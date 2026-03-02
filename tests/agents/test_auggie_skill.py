"""Tests for atk.agents.auggie_skill — Auggie skill injection via symlinks."""

from pathlib import Path

import pytest

from atk.agents.auggie_skill import inject_skill_symlink, remove_skill_symlink


class TestInjectSkillSymlink:
    """Tests for inject_skill_symlink."""

    def test_creates_symlink_in_rules_dir(self, tmp_path: Path) -> None:
        """Creates a symlink named atk-<plugin>.md in rules_dir."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugins" / plugin_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        rules_dir = tmp_path / "rules"

        # When
        injected = inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # Then
        assert injected is True
        symlink = rules_dir / f"atk-{plugin_name}.md"
        assert symlink.is_symlink()
        assert symlink.resolve() == skill_path.resolve()

    def test_creates_rules_dir_when_missing(self, tmp_path: Path) -> None:
        """Creates rules_dir (and parents) if they do not exist."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        rules_dir = tmp_path / "deep" / "nested" / "rules"
        assert not rules_dir.exists()

        # When
        inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # Then
        assert rules_dir.exists()
        symlink = rules_dir / f"atk-{plugin_name}.md"
        assert symlink.is_symlink()

    def test_idempotent_when_same_target(self, tmp_path: Path) -> None:
        """Returns False and leaves symlink unchanged when target matches."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        rules_dir = tmp_path / "rules"
        inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # When
        result = inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # Then
        assert result is False
        symlink = rules_dir / f"atk-{plugin_name}.md"
        assert symlink.is_symlink()

    def test_updates_symlink_when_target_differs(self, tmp_path: Path) -> None:
        """Replaces the symlink and returns True when target differs."""
        # Given
        plugin_name = "my-plugin"
        old_skill = tmp_path / "old" / "SKILL.md"
        new_skill = tmp_path / "new" / "SKILL.md"
        old_skill.parent.mkdir(parents=True)
        new_skill.parent.mkdir(parents=True)
        old_skill.write_text("# Old")
        new_skill.write_text("# New")
        rules_dir = tmp_path / "rules"
        inject_skill_symlink(plugin_name, old_skill, rules_dir=rules_dir)

        # When
        result = inject_skill_symlink(plugin_name, new_skill, rules_dir=rules_dir)

        # Then
        assert result is True
        symlink = rules_dir / f"atk-{plugin_name}.md"
        assert symlink.resolve() == new_skill.resolve()

    def test_raises_when_regular_file_exists(self, tmp_path: Path) -> None:
        """Raises FileExistsError if a regular file occupies the symlink path."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        (rules_dir / f"atk-{plugin_name}.md").write_text("user content")

        # When / Then
        with pytest.raises(FileExistsError):
            inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)


class TestRemoveSkillSymlink:
    """Tests for remove_skill_symlink."""

    def test_removes_existing_symlink(self, tmp_path: Path) -> None:
        """Deletes the symlink and returns True."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        rules_dir = tmp_path / "rules"
        inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # When
        removed = remove_skill_symlink(plugin_name, rules_dir=rules_dir)

        # Then
        assert removed is True
        assert not (rules_dir / f"atk-{plugin_name}.md").exists()

    def test_returns_false_when_not_present(self, tmp_path: Path) -> None:
        """Returns False when no symlink is present."""
        # Given
        plugin_name = "my-plugin"
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()

        # When
        removed = remove_skill_symlink(plugin_name, rules_dir=rules_dir)

        # Then
        assert removed is False

    def test_does_not_remove_regular_file(self, tmp_path: Path) -> None:
        """Leaves a regular file untouched and returns False."""
        # Given
        plugin_name = "my-plugin"
        rules_dir = tmp_path / "rules"
        rules_dir.mkdir()
        regular_file = rules_dir / f"atk-{plugin_name}.md"
        file_content = "user content"
        regular_file.write_text(file_content)

        # When
        removed = remove_skill_symlink(plugin_name, rules_dir=rules_dir)

        # Then
        assert removed is False
        assert regular_file.read_text() == file_content

    def test_skill_file_target_not_deleted(self, tmp_path: Path) -> None:
        """Only removes the symlink; the SKILL.md target is untouched."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_content = "# Skill"
        skill_path.write_text(skill_content)
        rules_dir = tmp_path / "rules"
        inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # When
        remove_skill_symlink(plugin_name, rules_dir=rules_dir)

        # Then
        assert skill_path.exists()
        assert skill_path.read_text() == skill_content

