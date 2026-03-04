"""Tests for atk.agents.auggie_skill — Auggie-specific symlink conventions."""

from pathlib import Path

from atk.agents.auggie_skill import inject_skill_symlink, remove_skill_symlink


class TestInjectSkillSymlink:
    """Auggie uses ``atk-<plugin>.md`` symlinks that point directly at SKILL.md."""

    def test_symlink_has_md_extension_and_targets_file(self, tmp_path: Path) -> None:
        """Symlink is named atk-<plugin>.md and points to the SKILL.md file itself."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugins" / plugin_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")
        rules_dir = tmp_path / "rules"

        # When
        inject_skill_symlink(plugin_name, skill_path, rules_dir=rules_dir)

        # Then
        symlink = rules_dir / f"atk-{plugin_name}.md"
        assert symlink.is_symlink()
        assert symlink.resolve() == skill_path.resolve()


class TestRemoveSkillSymlink:
    """Auggie remove targets the ``.md``-suffixed symlink name."""

    def test_removes_md_suffixed_symlink(self, tmp_path: Path) -> None:
        """Removes the atk-<plugin>.md symlink and returns True."""
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

