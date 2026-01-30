"""Tests for environment variable management."""

from pathlib import Path

from atk.env import EnvVarStatus, get_env_status, load_env_file, save_env_file
from atk.plugin_schema import EnvVarConfig, PluginSchema


class TestLoadEnvFile:
    """Tests for load_env_file function."""

    def test_loads_simple_env_file(self, tmp_path: Path) -> None:
        """Verify load_env_file reads key=value pairs."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=qux\n")

        result = load_env_file(env_file)

        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_returns_empty_dict_when_file_missing(self, tmp_path: Path) -> None:
        """Verify load_env_file returns empty dict for missing file."""
        env_file = tmp_path / ".env"

        result = load_env_file(env_file)

        assert result == {}

    def test_handles_empty_file(self, tmp_path: Path) -> None:
        """Verify load_env_file handles empty file."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        result = load_env_file(env_file)

        assert result == {}

    def test_ignores_comments(self, tmp_path: Path) -> None:
        """Verify load_env_file ignores comment lines."""
        env_file = tmp_path / ".env"
        env_file.write_text("# This is a comment\nFOO=bar\n# Another comment\n")

        result = load_env_file(env_file)

        assert result == {"FOO": "bar"}

    def test_handles_quoted_values(self, tmp_path: Path) -> None:
        """Verify load_env_file handles quoted values."""
        env_file = tmp_path / ".env"
        env_file.write_text('FOO="bar baz"\nQUX=\'quoted\'\n')

        result = load_env_file(env_file)

        assert result == {"FOO": "bar baz", "QUX": "quoted"}

    def test_handles_empty_values(self, tmp_path: Path) -> None:
        """Verify load_env_file handles empty values."""
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=\nBAR=value\n")

        result = load_env_file(env_file)

        assert result == {"FOO": "", "BAR": "value"}


class TestSaveEnvFile:
    """Tests for save_env_file function."""

    def test_saves_env_vars(self, tmp_path: Path) -> None:
        """Verify save_env_file writes key=value pairs."""
        env_file = tmp_path / ".env"
        foo_value = "bar"
        baz_value = "qux"

        save_env_file(env_file, {"FOO": foo_value, "BAZ": baz_value})

        content = env_file.read_text()
        assert content == f"FOO={foo_value}\nBAZ={baz_value}\n"

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Verify save_env_file creates file if it doesn't exist."""
        env_file = tmp_path / ".env"
        value = "bar"

        save_env_file(env_file, {"FOO": value})

        assert env_file.exists()
        assert env_file.read_text() == f"FOO={value}\n"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Verify save_env_file overwrites existing content."""
        env_file = tmp_path / ".env"
        env_file.write_text("OLD=value\n")
        new_value = "value"

        save_env_file(env_file, {"NEW": new_value})

        content = env_file.read_text()
        assert content == f"NEW={new_value}\n"

    def test_quotes_values_with_spaces(self, tmp_path: Path) -> None:
        """Verify save_env_file quotes values containing spaces."""
        env_file = tmp_path / ".env"
        value_with_spaces = "bar baz"

        save_env_file(env_file, {"FOO": value_with_spaces})

        content = env_file.read_text()
        assert content == f'FOO="{value_with_spaces}"\n'

    def test_includes_descriptions_as_comments(self, tmp_path: Path) -> None:
        """Verify save_env_file writes descriptions as comments."""
        env_file = tmp_path / ".env"
        var_name = "API_KEY"
        var_value = "secret123"
        var_description = "Your API key for the service"

        save_env_file(
            env_file,
            {var_name: var_value},
            descriptions={var_name: var_description},
        )

        content = env_file.read_text()
        expected = f"# {var_description}\n{var_name}={var_value}\n"
        assert content == expected

    def test_descriptions_only_for_vars_with_descriptions(self, tmp_path: Path) -> None:
        """Verify save_env_file only adds comments for vars with descriptions."""
        env_file = tmp_path / ".env"
        var_with_desc = "WITH_DESC"
        value1 = "value1"
        var_without_desc = "NO_DESC"
        value2 = "value2"
        description = "Has a description"

        save_env_file(
            env_file,
            {var_with_desc: value1, var_without_desc: value2},
            descriptions={var_with_desc: description},
        )

        content = env_file.read_text()
        expected = f"# {description}\n{var_with_desc}={value1}\n{var_without_desc}={value2}\n"
        assert content == expected


class TestEnvVarStatus:
    """Tests for EnvVarStatus dataclass."""

    def test_status_fields(self) -> None:
        """Verify EnvVarStatus has expected fields."""
        status = EnvVarStatus(
            name="FOO",
            required=True,
            secret=False,
            is_set=True,
            value="bar",
        )

        assert status.name == "FOO"
        assert status.required is True
        assert status.secret is False
        assert status.is_set is True
        assert status.value == "bar"

    def test_value_is_none_when_not_set(self) -> None:
        """Verify value is None when env var is not set."""
        status = EnvVarStatus(
            name="FOO",
            required=True,
            secret=False,
            is_set=False,
            value=None,
        )

        assert status.is_set is False
        assert status.value is None


class TestGetEnvStatus:
    """Tests for get_env_status function."""

    def _make_plugin(self, env_vars: list[dict]) -> PluginSchema:
        """Create a minimal plugin with env vars."""
        return PluginSchema(
            schema_version="1.0",
            name="TestPlugin",
            description="Test plugin",
            env_vars=[EnvVarConfig(**ev) for ev in env_vars],
        )

    def test_returns_status_for_each_env_var(self, tmp_path: Path) -> None:
        """Verify get_env_status returns status for each defined env var."""
        plugin = self._make_plugin([
            {"name": "FOO", "required": True},
            {"name": "BAR", "required": False},
        ])
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=value\n")

        result = get_env_status(plugin, tmp_path)

        assert len(result) == 2
        foo_status = next(s for s in result if s.name == "FOO")
        bar_status = next(s for s in result if s.name == "BAR")
        assert foo_status.is_set is True
        assert foo_status.value == "value"
        assert bar_status.is_set is False
        assert bar_status.value is None

    def test_returns_empty_list_when_no_env_vars(self, tmp_path: Path) -> None:
        """Verify get_env_status returns empty list when plugin has no env vars."""
        plugin = self._make_plugin([])

        result = get_env_status(plugin, tmp_path)

        assert result == []

    def test_marks_required_vars(self, tmp_path: Path) -> None:
        """Verify get_env_status marks required vars correctly."""
        plugin = self._make_plugin([
            {"name": "REQUIRED_VAR", "required": True},
            {"name": "OPTIONAL_VAR", "required": False},
        ])

        result = get_env_status(plugin, tmp_path)

        required = next(s for s in result if s.name == "REQUIRED_VAR")
        optional = next(s for s in result if s.name == "OPTIONAL_VAR")
        assert required.required is True
        assert optional.required is False

    def test_marks_secret_vars(self, tmp_path: Path) -> None:
        """Verify get_env_status marks secret vars correctly."""
        plugin = self._make_plugin([
            {"name": "API_KEY", "secret": True},
            {"name": "PUBLIC_VAR", "secret": False},
        ])

        result = get_env_status(plugin, tmp_path)

        secret = next(s for s in result if s.name == "API_KEY")
        public = next(s for s in result if s.name == "PUBLIC_VAR")
        assert secret.secret is True
        assert public.secret is False

    def test_checks_system_environment(self, tmp_path: Path, monkeypatch) -> None:
        """Verify get_env_status checks system environment when not in .env."""
        plugin = self._make_plugin([{"name": "SYSTEM_VAR", "required": True}])
        monkeypatch.setenv("SYSTEM_VAR", "from_system")

        result = get_env_status(plugin, tmp_path)

        status = result[0]
        assert status.is_set is True
        assert status.value == "from_system"

    def test_env_file_takes_precedence_over_system(self, tmp_path: Path, monkeypatch) -> None:
        """Verify .env file values take precedence over system environment."""
        plugin = self._make_plugin([{"name": "MY_VAR", "required": True}])
        monkeypatch.setenv("MY_VAR", "from_system")
        env_file = tmp_path / ".env"
        env_file.write_text("MY_VAR=from_file\n")

        result = get_env_status(plugin, tmp_path)

        status = result[0]
        assert status.value == "from_file"
