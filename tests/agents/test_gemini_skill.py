"""Tests for atk.agents.gemini_skill — Gemini-specific symlink conventions."""

from pathlib import Path

from atk.agents.gemini_skill import inject_skill_symlink, remove_skill_symlink


class TestInjectSkillSymlink:
    """Gemini uses ``atk-<plugin>`` symlinks that point at the SKILL.md parent directory."""

    def test_symlink_has_no_extension_and_targets_parent_dir(self, tmp_path: Path) -> None:
        """Symlink is named atk-<plugin> (no .md) and points to the plugin directory."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugins" / plugin_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        skills_dir = tmp_path / "skills"

        # When
        inject_skill_symlink(plugin_name, skill_path, skills_dir=skills_dir)

        # Then
        symlink = skills_dir / f"atk-{plugin_name}"
        assert symlink.is_symlink()
        assert symlink.resolve() == skill_path.parent.resolve()


class TestRemoveSkillSymlink:
    """Gemini remove targets the extension-free symlink name."""

    def test_removes_extensionless_symlink(self, tmp_path: Path) -> None:
        """Removes the atk-<plugin> symlink (no .md) and returns True."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        skills_dir = tmp_path / "skills"
        inject_skill_symlink(plugin_name, skill_path, skills_dir=skills_dir)

        # When
        removed = remove_skill_symlink(plugin_name, skills_dir=skills_dir)

        # Then
        assert removed is True
        assert not (skills_dir / f"atk-{plugin_name}").exists()

