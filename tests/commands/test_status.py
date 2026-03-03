"""Tests for commands/status helpers."""

from atk.commands.status import _format_env_status as format_env_status


class TestFormatEnvStatus:
    """Tests for format_env_status helper function."""

    def test_shows_checkmark_when_all_required_set_with_unset_optional(self) -> None:
        """Verify checkmark shown when all required vars set (even with unset optional vars).

        Regression test: Bug where function returned "-" instead of "✓" when
        all required vars were set but optional vars were unset.
        """
        # Given
        missing_required_vars = []
        unset_optional_count = 1
        total_env_vars = 2
        expected_result = "[green]✓[/green]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_checkmark_when_all_vars_set(self) -> None:
        """Verify checkmark shown when all vars (required and optional) are set."""
        # Given
        missing_required_vars = []
        unset_optional_count = 0
        total_env_vars = 2
        expected_result = "[green]✓[/green]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_dash_when_no_env_vars_defined(self) -> None:
        """Verify dash shown when plugin has no env vars defined."""
        # Given
        missing_required_vars = []
        unset_optional_count = 0
        total_env_vars = 0
        expected_result = "-"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_missing_required_vars_by_name(self) -> None:
        """Verify missing required vars are listed by name."""
        # Given
        var1_name = "API_KEY"
        var2_name = "SECRET_KEY"
        missing_required_vars = [var1_name, var2_name]
        unset_optional_count = 0
        total_env_vars = 3
        expected_result = f"[red]! {var1_name}, {var2_name}[/red]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

    def test_shows_optional_count_with_missing_required(self) -> None:
        """Verify optional count shown when required vars missing."""
        # Given
        var_name = "API_KEY"
        missing_required_vars = [var_name]
        unset_optional_count = 2
        total_env_vars = 3
        expected_result = f"[red]! {var_name}[/red] [dim](+{unset_optional_count} optional)[/dim]"

        # When
        result = format_env_status(missing_required_vars, unset_optional_count, total_env_vars)

        # Then
        assert result == expected_result

