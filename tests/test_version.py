"""Test ATK version and basic imports."""

from importlib.metadata import version

from typer.testing import CliRunner

from atk import __version__
from atk.cli import app
from atk.init import init_atk_home


class TestVersion:
    """Tests for ATK version and package structure."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_version_is_defined(self) -> None:
        """Verify that __version__ is defined and matches pyproject.toml."""
        # Given - version from pyproject.toml via package metadata
        expected = version("atk-cli")

        # When
        actual = __version__

        # Then
        assert actual == expected

    def test_cli_app_is_importable(self) -> None:
        """Verify that the CLI app can be imported."""
        # Given/When - app is imported at module level

        # Then
        assert app is not None
        assert app.info.name == "atk"

    def test_version_flag_shows_banner(self) -> None:
        """Verify that --version flag outputs the banner with version."""
        # Given
        pkg_version = version("atk-cli")

        # When
        result = self.runner.invoke(app, ["--version"])

        # Then
        assert result.exit_code == 0
        # Banner contains version info
        assert f"v{pkg_version}" in result.output
        assert "atk" in result.output
        assert "AI Toolkit" in result.output

    def test_status_command_exists(self, tmp_path, monkeypatch) -> None:
        """Verify that status command is available."""
        # Given
        monkeypatch.setenv("ATK_HOME", str(tmp_path))
        init_atk_home(tmp_path)

        # When
        result = self.runner.invoke(app, ["status"])

        # Then
        assert result.exit_code == 0
        assert "No plugins installed" in result.output

