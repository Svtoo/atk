"""Tests for commands/search helpers."""

from atk.commands.search import filter_registry_plugins
from atk.registry_schema import RegistryPluginEntry


def _entry(name: str, description: str) -> RegistryPluginEntry:
    return RegistryPluginEntry(name=name, path=f"plugins/{name}", description=description)


class TestFilterRegistryPlugins:
    """Tests for the filter_registry_plugins filtering logic."""

    def test_matches_by_name_substring(self) -> None:
        """Returns plugins whose name contains the query."""
        # Given
        lang_name = "langfuse"
        plugins = [
            _entry(lang_name, "LLM observability platform"),
            _entry("openmemory", "Persistent memory for AI agents"),
        ]
        query = "lang"

        # When
        result = filter_registry_plugins(plugins, query)

        # Then
        assert len(result) == 1
        assert result[0].name == lang_name

    def test_matches_by_description_substring(self) -> None:
        """Returns plugins whose description contains the query."""
        # Given
        mem_name = "openmemory"
        plugins = [
            _entry("langfuse", "LLM observability platform"),
            _entry(mem_name, "Persistent memory for AI agents"),
        ]
        query = "memory"

        # When
        result = filter_registry_plugins(plugins, query)

        # Then
        assert len(result) == 1
        assert result[0].name == mem_name

    def test_match_is_case_insensitive(self) -> None:
        """Query matching ignores case in both name and description."""
        # Given
        gh_name = "github"
        plugins = [_entry(gh_name, "GitHub integration via MCP")]
        query = "GITHUB"

        # When
        result = filter_registry_plugins(plugins, query)

        # Then
        assert len(result) == 1
        assert result[0].name == gh_name

    def test_returns_empty_list_when_no_match(self) -> None:
        """Returns empty list when no plugin matches."""
        # Given
        plugins = [
            _entry("langfuse", "LLM observability platform"),
            _entry("openmemory", "Persistent memory for AI agents"),
        ]
        query = "zzznomatch"

        # When
        result = filter_registry_plugins(plugins, query)

        # Then
        assert result == []

    def test_returns_all_matching_plugins(self) -> None:
        """Returns every plugin that matches, not just the first one."""
        # Given
        git_local_name = "git-local"
        github_name = "github"
        plugins = [
            _entry(git_local_name, "Git operations on local repos via MCP"),
            _entry(github_name, "GitHub integration via MCP"),
            _entry("langfuse", "LLM observability platform"),
        ]
        query = "git"

        # When
        result = filter_registry_plugins(plugins, query)

        # Then
        result_names = [p.name for p in result]
        assert git_local_name in result_names
        assert github_name in result_names
        assert len(result) == 2

