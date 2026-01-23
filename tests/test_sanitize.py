"""Tests for directory name sanitization."""

import pytest

from atk.sanitize import sanitize_directory_name


class TestSanitizeDirectoryName:
    """Tests for sanitize_directory_name function."""

    @pytest.mark.parametrize(
        ("display_name", "expected"),
        [
            pytest.param("OpenMemory", "openmemory", id="camelcase"),
            pytest.param("My Plugin", "my-plugin", id="spaces-to-hyphens"),
            pytest.param("my_plugin", "my-plugin", id="underscores-to-hyphens"),
            pytest.param("My Cool Plugin", "my-cool-plugin", id="multiple-words"),
            pytest.param("  trimmed  ", "trimmed", id="trim-whitespace"),
            pytest.param("foo--bar", "foo-bar", id="collapse-hyphens"),
            pytest.param("foo___bar", "foo-bar", id="collapse-underscores"),
            pytest.param("UPPERCASE", "uppercase", id="all-uppercase"),
            pytest.param("plugin-name", "plugin-name", id="already-valid"),
            pytest.param("ab", "ab", id="minimum-length"),
        ],
    )
    def test_valid_names(self, display_name: str, expected: str) -> None:
        """Verify sanitization produces expected directory names."""
        # When
        result = sanitize_directory_name(display_name)

        # Then
        assert result == expected

    @pytest.mark.parametrize(
        ("display_name", "expected"),
        [
            pytest.param("123plugin", "a123plugin", id="starts-with-number"),
            pytest.param("-123plugin", "a123plugin", id="hyphen-then-number"),
        ],
    )
    def test_prefix_when_starts_invalid(self, display_name: str, expected: str) -> None:
        """Verify 'a' prefix added when name starts with non-letter after cleanup."""
        # When
        result = sanitize_directory_name(display_name)

        # Then
        assert result == expected

    @pytest.mark.parametrize(
        "display_name",
        [
            pytest.param("", id="empty-string"),
            pytest.param("   ", id="only-whitespace"),
            pytest.param("a", id="too-short"),
        ],
    )
    def test_invalid_names_raise(self, display_name: str) -> None:
        """Verify ValueError for names that cannot be sanitized."""
        # When/Then
        with pytest.raises(ValueError, match="cannot be sanitized"):
            sanitize_directory_name(display_name)

    @pytest.mark.parametrize(
        ("display_name", "expected"),
        [
            pytest.param("plugin@name", "pluginname", id="at-symbol-stripped"),
            pytest.param("plugin#name", "pluginname", id="hash-stripped"),
            pytest.param("plugin$name", "pluginname", id="dollar-stripped"),
            pytest.param("plugin%name", "pluginname", id="percent-stripped"),
            pytest.param("plugin&name", "pluginname", id="ampersand-stripped"),
            pytest.param("plugin*name", "pluginname", id="asterisk-stripped"),
            pytest.param("plugin!name", "pluginname", id="exclamation-stripped"),
            pytest.param("plugin?name", "pluginname", id="question-stripped"),
            pytest.param("plugin/name", "pluginname", id="slash-stripped"),
            pytest.param("plugin\\name", "pluginname", id="backslash-stripped"),
            pytest.param("plugin.name", "pluginname", id="dot-stripped"),
            pytest.param("plugin:name", "pluginname", id="colon-stripped"),
            pytest.param("plugin;name", "pluginname", id="semicolon-stripped"),
            pytest.param("plugin'name", "pluginname", id="single-quote-stripped"),
            pytest.param('plugin"name', "pluginname", id="double-quote-stripped"),
            pytest.param("plugin`name", "pluginname", id="backtick-stripped"),
            pytest.param("plugin(name)", "pluginname", id="parens-stripped"),
            pytest.param("plugin[name]", "pluginname", id="brackets-stripped"),
            pytest.param("plugin{name}", "pluginname", id="braces-stripped"),
            pytest.param("plugin<name>", "pluginname", id="angle-brackets-stripped"),
            pytest.param("plugin|name", "pluginname", id="pipe-stripped"),
            pytest.param("plugin~name", "pluginname", id="tilde-stripped"),
            pytest.param("plugin^name", "pluginname", id="caret-stripped"),
            pytest.param("plugin=name", "pluginname", id="equals-stripped"),
            pytest.param("plugin+name", "pluginname", id="plus-stripped"),
        ],
    )
    def test_special_characters_stripped(self, display_name: str, expected: str) -> None:
        """Verify special characters are stripped from names."""
        # When
        result = sanitize_directory_name(display_name)

        # Then
        assert result == expected

    @pytest.mark.parametrize(
        ("display_name", "expected"),
        [
            pytest.param("$(rm -rf /)", "rm-rf", id="command-substitution"),
            pytest.param("`rm -rf /`", "rm-rf", id="backtick-command"),
            pytest.param("foo; rm -rf /", "foo-rm-rf", id="semicolon-injection"),
            pytest.param("foo && rm -rf /", "foo-rm-rf", id="and-injection"),
            pytest.param("foo || rm -rf /", "foo-rm-rf", id="or-injection"),
            pytest.param("foo | cat /etc/passwd", "foo-cat-etcpasswd", id="pipe-injection"),
            pytest.param("../../../etc/passwd", "etcpasswd", id="path-traversal"),
            pytest.param("foo\nbar", "foobar", id="newline-injection"),
            pytest.param("foo\tbar", "foobar", id="tab-injection"),
            pytest.param("foo\rbar", "foobar", id="carriage-return"),
            pytest.param("foo\x00bar", "foobar", id="null-byte"),
        ],
    )
    def test_injection_attempts_sanitized(self, display_name: str, expected: str) -> None:
        """Verify malicious injection attempts are safely sanitized."""
        # When
        result = sanitize_directory_name(display_name)

        # Then
        assert result == expected

