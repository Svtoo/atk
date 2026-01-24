"""Test ATK version and basic imports."""

from typer.testing import CliRunner


class TestVersion:
    """Tests for ATK version and package structure."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.expected_version = "0.1.0"
        self.runner = CliRunner()

    def test_version_is_defined(self) -> None:
        """Verify that __version__ is defined and matches expected value."""
        # Given
        expected = self.expected_version

        # When
        from atk import __version__

        # Then
        assert __version__ == expected

    def test_cli_app_is_importable(self) -> None:
        """Verify that the CLI app can be imported."""
        # When
        from atk.cli import app

        # Then
        assert app is not None
        assert app.info.name == "atk"

    def test_version_flag_shows_banner(self) -> None:
        """Verify that --version flag outputs the banner with version."""
        # Given
        from atk.cli import app

        version = self.expected_version

        # When
        result = self.runner.invoke(app, ["--version"])

        # Then
        assert result.exit_code == 0
        # Banner contains version info
        assert f"v{version}" in result.output
        assert "atk" in result.output
        assert "AI Toolkit" in result.output

    def test_status_command_exists(self, tmp_path, monkeypatch) -> None:
        """Verify that status command is available."""
        from atk.cli import app
        from atk.init import init_atk_home

        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)

        result = self.runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "No plugins installed" in result.output

