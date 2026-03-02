"""Tests for atk.agents.opencode_skill — OpenCode skill injection via opencode.jsonc."""

import json
from pathlib import Path

from atk.agents.opencode_skill import (
    inject_skill_instruction,
    remove_opencode_mcp_entry,
    remove_opencode_plugin,
    remove_skill_instruction,
)


class TestInjectSkillInstruction:
    """Tests for inject_skill_instruction."""

    def test_creates_config_when_missing(self, tmp_path: Path) -> None:
        """Creates opencode.jsonc (and parent dirs) if absent."""
        # Given
        config_path = tmp_path / ".config" / "opencode" / "opencode.jsonc"
        skill_path = tmp_path / "plugin" / "SKILL.md"
        skill_path.parent.mkdir(parents=True)
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_instruction(skill_path, config_path=config_path)

        # Then
        assert injected is True
        assert config_path.exists()
        data = json.loads(config_path.read_text())
        resolved = str(skill_path.resolve())
        assert data["instructions"] == [resolved]

    def test_appends_to_existing_instructions(self, tmp_path: Path) -> None:
        """Appends to an existing instructions array."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        existing_instruction = "/some/other/file.md"
        config_path.write_text(json.dumps({"instructions": [existing_instruction]}))
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        injected = inject_skill_instruction(skill_path, config_path=config_path)

        # Then
        assert injected is True
        data = json.loads(config_path.read_text())
        resolved = str(skill_path.resolve())
        assert existing_instruction in data["instructions"]
        assert resolved in data["instructions"]

    def test_idempotent_when_already_present(self, tmp_path: Path) -> None:
        """Returns False and does not duplicate an existing entry."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        inject_skill_instruction(skill_path, config_path=config_path)

        # When
        injected_again = inject_skill_instruction(skill_path, config_path=config_path)

        # Then
        assert injected_again is False
        data = json.loads(config_path.read_text())
        resolved = str(skill_path.resolve())
        assert data["instructions"].count(resolved) == 1

    def test_preserves_other_config_keys(self, tmp_path: Path) -> None:
        """Does not clobber other keys in the config file."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        original = {"theme": "dark", "mcp": {"my-tool": {"command": "run"}}}
        config_path.write_text(json.dumps(original))
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        inject_skill_instruction(skill_path, config_path=config_path)

        # Then
        data = json.loads(config_path.read_text())
        assert data["theme"] == "dark"
        assert data["mcp"] == {"my-tool": {"command": "run"}}


class TestRemoveSkillInstruction:
    """Tests for remove_skill_instruction."""

    def test_removes_existing_instruction(self, tmp_path: Path) -> None:
        """Removes a previously injected instruction."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        inject_skill_instruction(skill_path, config_path=config_path)

        # When
        removed = remove_skill_instruction(skill_path, config_path=config_path)

        # Then
        assert removed is True
        data = json.loads(config_path.read_text())
        resolved = str(skill_path.resolve())
        assert resolved not in data["instructions"]

    def test_returns_false_when_not_present(self, tmp_path: Path) -> None:
        """Returns False when the instruction is not in the array."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        config_path.write_text(json.dumps({"instructions": []}))
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        removed = remove_skill_instruction(skill_path, config_path=config_path)

        # Then
        assert removed is False

    def test_returns_false_when_config_missing(self, tmp_path: Path) -> None:
        """Returns False gracefully when config file does not exist."""
        # Given
        config_path = tmp_path / "nonexistent" / "opencode.jsonc"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        removed = remove_skill_instruction(skill_path, config_path=config_path)

        # Then
        assert removed is False


class TestRemoveOpencodeMcpEntry:
    """Tests for remove_opencode_mcp_entry."""

    def test_removes_existing_mcp_entry(self, tmp_path: Path) -> None:
        """Removes a named MCP entry from the config."""
        # Given
        plugin_name = "my-plugin"
        config_path = tmp_path / "opencode.jsonc"
        config_data = {"mcp": {plugin_name: {"command": "run-it"}}}
        config_path.write_text(json.dumps(config_data))

        # When
        removed = remove_opencode_mcp_entry(plugin_name, config_path=config_path)

        # Then
        assert removed is True
        data = json.loads(config_path.read_text())
        assert plugin_name not in data["mcp"]

    def test_returns_false_when_entry_not_present(self, tmp_path: Path) -> None:
        """Returns False when the MCP entry does not exist."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        config_path.write_text(json.dumps({"mcp": {}}))

        # When
        removed = remove_opencode_mcp_entry("nonexistent", config_path=config_path)

        # Then
        assert removed is False

    def test_returns_false_when_config_missing(self, tmp_path: Path) -> None:
        """Returns False gracefully when config file does not exist."""
        # Given
        config_path = tmp_path / "nonexistent" / "opencode.jsonc"

        # When
        removed = remove_opencode_mcp_entry("my-plugin", config_path=config_path)

        # Then
        assert removed is False


class TestRemoveOpencodePlugin:
    """Tests for remove_opencode_plugin (combined MCP + skill removal)."""

    def test_removes_both_mcp_and_skill(self, tmp_path: Path) -> None:
        """Removes MCP entry and skill instruction in a single write."""
        # Given
        plugin_name = "my-plugin"
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")
        resolved = str(skill_path.resolve())
        config_path = tmp_path / "opencode.jsonc"
        config_data = {
            "mcp": {plugin_name: {"command": "run"}},
            "instructions": [resolved],
        }
        config_path.write_text(json.dumps(config_data))

        # When
        mcp_removed, skill_removed = remove_opencode_plugin(
            plugin_name, skill_path, config_path=config_path
        )

        # Then
        assert mcp_removed is True
        assert skill_removed is True
        data = json.loads(config_path.read_text())
        assert plugin_name not in data["mcp"]
        assert resolved not in data["instructions"]

    def test_removes_only_mcp_when_no_skill_path(self, tmp_path: Path) -> None:
        """Only removes MCP entry when skill_path is None."""
        # Given
        plugin_name = "my-plugin"
        config_path = tmp_path / "opencode.jsonc"
        config_data = {"mcp": {plugin_name: {"command": "run"}}}
        config_path.write_text(json.dumps(config_data))

        # When
        mcp_removed, skill_removed = remove_opencode_plugin(
            plugin_name, None, config_path=config_path
        )

        # Then
        assert mcp_removed is True
        assert skill_removed is False

    def test_returns_false_false_when_neither_present(self, tmp_path: Path) -> None:
        """Returns (False, False) when nothing matches."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        config_path.write_text(json.dumps({"mcp": {}, "instructions": []}))
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        mcp_removed, skill_removed = remove_opencode_plugin(
            "nonexistent", skill_path, config_path=config_path
        )

        # Then
        assert mcp_removed is False
        assert skill_removed is False

    def test_does_not_write_when_nothing_to_remove(self, tmp_path: Path) -> None:
        """Does not modify the file when neither entry nor skill is present."""
        # Given
        config_path = tmp_path / "opencode.jsonc"
        original_content = json.dumps({"mcp": {}, "instructions": []})
        config_path.write_text(original_content)
        mtime_before = config_path.stat().st_mtime_ns
        skill_path = tmp_path / "SKILL.md"
        skill_path.write_text("# Skill")

        # When
        remove_opencode_plugin("nonexistent", skill_path, config_path=config_path)

        # Then — file should not have been rewritten
        mtime_after = config_path.stat().st_mtime_ns
        assert mtime_before == mtime_after

