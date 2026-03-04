"""Tests for atk.agents.symlink_skill — generic symlink create/remove primitives."""

from pathlib import Path

import pytest

from atk.agents.symlink_skill import create_skill_symlink, remove_skill_symlink


class TestCreateSkillSymlink:
    """Tests for create_skill_symlink."""

    def test_creates_symlink_pointing_to_target(self, tmp_path: Path) -> None:
        """Creates a symlink at the given path pointing to the given target."""
        # Given
        target = tmp_path / "plugin" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Skill")
        symlink = tmp_path / "rules" / "atk-my-plugin.md"

        # When
        created = create_skill_symlink(symlink, target.resolve())

        # Then
        assert created is True
        assert symlink.is_symlink()
        assert symlink.resolve() == target.resolve()

    def test_creates_parent_dirs_when_missing(self, tmp_path: Path) -> None:
        """Creates the symlink's parent directories if they do not exist."""
        # Given
        target = tmp_path / "plugin" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Skill")
        symlink = tmp_path / "deep" / "nested" / "rules" / "atk-plugin.md"
        assert not symlink.parent.exists()

        # When
        create_skill_symlink(symlink, target.resolve())

        # Then
        assert symlink.parent.exists()
        assert symlink.is_symlink()

    def test_idempotent_when_same_target(self, tmp_path: Path) -> None:
        """Returns False and leaves the symlink unchanged when target already matches."""
        # Given
        target = tmp_path / "plugin" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Skill")
        symlink = tmp_path / "rules" / "atk-plugin.md"
        create_skill_symlink(symlink, target.resolve())

        # When
        result = create_skill_symlink(symlink, target.resolve())

        # Then
        assert result is False
        assert symlink.is_symlink()
        assert symlink.resolve() == target.resolve()

    def test_updates_symlink_when_target_differs(self, tmp_path: Path) -> None:
        """Replaces the symlink and returns True when the target has changed."""
        # Given
        old_target = tmp_path / "old" / "SKILL.md"
        new_target = tmp_path / "new" / "SKILL.md"
        old_target.parent.mkdir(parents=True)
        new_target.parent.mkdir(parents=True)
        old_target.write_text("# Old")
        new_target.write_text("# New")
        symlink = tmp_path / "rules" / "atk-plugin.md"
        create_skill_symlink(symlink, old_target.resolve())

        # When
        result = create_skill_symlink(symlink, new_target.resolve())

        # Then
        assert result is True
        assert symlink.resolve() == new_target.resolve()

    def test_raises_when_non_symlink_occupies_path(self, tmp_path: Path) -> None:
        """Raises FileExistsError if a regular file occupies the symlink path."""
        # Given
        target = tmp_path / "plugin" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Skill")
        symlink = tmp_path / "rules" / "atk-plugin.md"
        symlink.parent.mkdir()
        symlink.write_text("user content")

        # When / Then
        with pytest.raises(FileExistsError):
            create_skill_symlink(symlink, target.resolve())


class TestRemoveSkillSymlink:
    """Tests for remove_skill_symlink."""

    def test_removes_existing_symlink(self, tmp_path: Path) -> None:
        """Deletes the symlink and returns True."""
        # Given
        target = tmp_path / "plugin" / "SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_text("# Skill")
        symlink = tmp_path / "rules" / "atk-plugin.md"
        create_skill_symlink(symlink, target.resolve())

        # When
        removed = remove_skill_symlink(symlink)

        # Then
        assert removed is True
        assert not symlink.exists()

    def test_returns_false_when_symlink_not_present(self, tmp_path: Path) -> None:
        """Returns False when no symlink exists at the path."""
        # Given
        symlink = tmp_path / "rules" / "atk-plugin.md"
        symlink.parent.mkdir()

        # When
        removed = remove_skill_symlink(symlink)

        # Then
        assert removed is False

    def test_does_not_remove_regular_file(self, tmp_path: Path) -> None:
        """Leaves a regular file untouched and returns False."""
        # Given
        symlink = tmp_path / "rules" / "atk-plugin.md"
        symlink.parent.mkdir()
        file_content = "user content"
        symlink.write_text(file_content)

        # When
        removed = remove_skill_symlink(symlink)

        # Then
        assert removed is False
        assert symlink.read_text() == file_content

    def test_target_not_deleted_when_symlink_removed(self, tmp_path: Path) -> None:
        """Only removes the symlink; the target file is untouched."""
        # Given
        target = tmp_path / "plugin" / "SKILL.md"
        target.parent.mkdir(parents=True)
        skill_content = "# Skill"
        target.write_text(skill_content)
        symlink = tmp_path / "rules" / "atk-plugin.md"
        create_skill_symlink(symlink, target.resolve())

        # When
        remove_skill_symlink(symlink)

        # Then
        assert target.exists()
        assert target.read_text() == skill_content

