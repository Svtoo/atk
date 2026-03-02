"""Tests for atk.agents.claude_skill — Claude Code skill injection."""

from pathlib import Path

from atk.agents.claude_skill import inject_skill_reference, remove_skill_reference
from atk.agents.managed_section import ATK_SECTION_BEGIN, ATK_SECTION_END


class TestInjectSkillReference:
    """Tests for inject_skill_reference."""

    def test_creates_claude_md_when_missing(self, tmp_path: Path) -> None:
        """Creates CLAUDE.md (and its parent dir) if absent."""
        # Given
        claude_md = tmp_path / ".claude" / "CLAUDE.md"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected is True
        assert claude_md.exists()
        content = claude_md.read_text()
        assert ATK_SECTION_BEGIN in content
        assert ATK_SECTION_END in content
        reference = f"@{skill_path.resolve()}"
        assert reference in content

    def test_adds_atk_section_to_existing_file_without_section(self, tmp_path: Path) -> None:
        """Appends ATK section to a CLAUDE.md that has user content."""
        # Given
        claude_md = tmp_path / "CLAUDE.md"
        user_content = "# My notes\n\nSome user content.\n"
        claude_md.write_text(user_content)
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected is True
        content = claude_md.read_text()
        assert "Some user content." in content
        assert content.index(ATK_SECTION_BEGIN) > content.index("Some user content.")
        reference = f"@{skill_path.resolve()}"
        assert reference in content

    def test_idempotent_when_reference_already_present(self, tmp_path: Path) -> None:
        """Returns False and does not duplicate an existing reference."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "CLAUDE.md"
        inject_skill_reference(skill_path, claude_md_path=claude_md)

        # When
        injected_again = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected_again is False
        content = claude_md.read_text()
        reference = f"@{skill_path.resolve()}"
        assert content.count(reference) == 1

    def test_multiple_plugins_all_appear_in_section(self, tmp_path: Path) -> None:
        """Multiple plugins each get their own reference line inside the ATK section."""
        # Given
        claude_md = tmp_path / "CLAUDE.md"
        skill_a = tmp_path / "plugin-a" / "SKILL.md"
        skill_b = tmp_path / "plugin-b" / "SKILL.md"
        skill_a.parent.mkdir()
        skill_b.parent.mkdir()
        skill_a.write_text("# A")
        skill_b.write_text("# B")

        # When
        inject_skill_reference(skill_a, claude_md_path=claude_md)
        inject_skill_reference(skill_b, claude_md_path=claude_md)

        # Then
        content = claude_md.read_text()
        ref_a = f"@{skill_a.resolve()}"
        ref_b = f"@{skill_b.resolve()}"
        assert ref_a in content
        assert ref_b in content
        begin = content.index(ATK_SECTION_BEGIN)
        end = content.index(ATK_SECTION_END)
        section = content[begin:end]
        assert ref_a in section
        assert ref_b in section

    def test_references_outside_atk_section_are_not_deduplicated(self, tmp_path: Path) -> None:
        """A reference placed by the user outside the ATK section does not block injection."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        reference = f"@{skill_path.resolve()}"
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(f"{reference}\n")

        # When
        injected = inject_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert injected is True
        content = claude_md.read_text()
        assert ATK_SECTION_BEGIN in content


class TestRemoveSkillReference:
    """Tests for remove_skill_reference."""

    def test_removes_existing_reference(self, tmp_path: Path) -> None:
        """Removes a reference previously added by inject."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "CLAUDE.md"
        inject_skill_reference(skill_path, claude_md_path=claude_md)

        # When
        removed = remove_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert removed is True
        content = claude_md.read_text()
        reference = f"@{skill_path.resolve()}"
        assert reference not in content

    def test_returns_false_when_not_present(self, tmp_path: Path) -> None:
        """Returns False when the reference does not exist."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text(f"{ATK_SECTION_BEGIN}\n{ATK_SECTION_END}\n")

        # When
        removed = remove_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert removed is False

    def test_returns_false_when_claude_md_missing(self, tmp_path: Path) -> None:
        """Returns False gracefully when CLAUDE.md does not exist."""
        # Given
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        claude_md = tmp_path / "nonexistent" / "CLAUDE.md"

        # When
        removed = remove_skill_reference(skill_path, claude_md_path=claude_md)

        # Then
        assert removed is False

