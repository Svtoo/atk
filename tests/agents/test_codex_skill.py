"""Tests for atk.agents.codex_skill — Codex skill injection via read-directives."""

from pathlib import Path

from atk.agents.codex_skill import inject_skill_directive, remove_skill_directive
from atk.agents.managed_section import ATK_SECTION_BEGIN, ATK_SECTION_END


class TestInjectSkillDirective:
    """Tests for inject_skill_directive."""

    def test_creates_agents_md_when_missing(self, tmp_path: Path) -> None:
        """Creates AGENTS.md (and its parent dir) if absent."""
        # Given
        agents_md = tmp_path / ".codex" / "AGENTS.md"
        plugin_name = "my-plugin"
        skill_path = tmp_path / "plugins" / plugin_name / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert injected is True
        assert agents_md.exists()
        content = agents_md.read_text()
        assert ATK_SECTION_BEGIN in content
        assert ATK_SECTION_END in content
        expected_directive = f"Read {skill_path.resolve()} for instructions on using the {plugin_name} MCP tools."
        assert expected_directive in content

    def test_replaces_broken_symlink(self, tmp_path: Path) -> None:
        """Replaces a broken symlink with a fresh file containing the directive."""
        # Given
        agents_md = tmp_path / "AGENTS.md"
        broken_target = tmp_path / "nonexistent" / "target.md"
        agents_md.symlink_to(broken_target)
        assert agents_md.is_symlink()
        assert not agents_md.exists()  # broken symlink

        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert injected is True
        assert not agents_md.is_symlink()  # symlink replaced with regular file
        assert agents_md.exists()
        content = agents_md.read_text()
        expected_directive = f"Read {skill_path.resolve()} for instructions on using the {plugin_name} MCP tools."
        assert expected_directive in content

    def test_adds_atk_section_to_existing_file(self, tmp_path: Path) -> None:
        """Appends ATK section to an AGENTS.md that has user content."""
        # Given
        agents_md = tmp_path / "AGENTS.md"
        user_content = "# My Codex Agent Notes\n\nSome user content.\n"
        agents_md.write_text(user_content)
        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert injected is True
        content = agents_md.read_text()
        assert "Some user content." in content
        assert content.index(ATK_SECTION_BEGIN) > content.index("Some user content.")

    def test_idempotent_when_directive_already_present(self, tmp_path: Path) -> None:
        """Returns False and does not duplicate an existing directive."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        agents_md = tmp_path / "AGENTS.md"
        inject_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # When
        injected_again = inject_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert injected_again is False
        content = agents_md.read_text()
        expected_directive = f"Read {skill_path.resolve()} for instructions on using the {plugin_name} MCP tools."
        assert content.count(expected_directive) == 1

    def test_multiple_plugins_all_appear_in_section(self, tmp_path: Path) -> None:
        """Multiple plugins each get their own directive inside the ATK section."""
        # Given
        agents_md = tmp_path / "AGENTS.md"
        plugin_a = "plugin-a"
        plugin_b = "plugin-b"
        skill_a = tmp_path / plugin_a / "SKILL.md"
        skill_b = tmp_path / plugin_b / "SKILL.md"
        skill_a.parent.mkdir()
        skill_b.parent.mkdir()
        skill_a.write_text("# A")
        skill_b.write_text("# B")

        # When
        inject_skill_directive(plugin_a, skill_a, agents_md_path=agents_md)
        inject_skill_directive(plugin_b, skill_b, agents_md_path=agents_md)

        # Then
        content = agents_md.read_text()
        directive_a = f"Read {skill_a.resolve()} for instructions on using the {plugin_a} MCP tools."
        directive_b = f"Read {skill_b.resolve()} for instructions on using the {plugin_b} MCP tools."
        assert directive_a in content
        assert directive_b in content
        begin = content.index(ATK_SECTION_BEGIN)
        end = content.index(ATK_SECTION_END)
        section = content[begin:end]
        assert directive_a in section
        assert directive_b in section


class TestRemoveSkillDirective:
    """Tests for remove_skill_directive."""

    def test_removes_existing_directive(self, tmp_path: Path) -> None:
        """Removes a directive previously added by inject."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        agents_md = tmp_path / "AGENTS.md"
        inject_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # When
        removed = remove_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert removed is True
        content = agents_md.read_text()
        expected_directive = f"Read {skill_path.resolve()} for instructions on using the {plugin_name} MCP tools."
        assert expected_directive not in content

    def test_returns_false_when_not_present(self, tmp_path: Path) -> None:
        """Returns False when the directive does not exist."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text(f"{ATK_SECTION_BEGIN}\n{ATK_SECTION_END}\n")

        # When
        removed = remove_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert removed is False

    def test_returns_false_when_agents_md_missing(self, tmp_path: Path) -> None:
        """Returns False gracefully when AGENTS.md does not exist."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        agents_md = tmp_path / "nonexistent" / "AGENTS.md"

        # When
        removed = remove_skill_directive(plugin_name, skill_path, agents_md_path=agents_md)

        # Then
        assert removed is False

