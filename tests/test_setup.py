from pathlib import Path

from atk.plugin_schema import PLUGIN_SCHEMA_VERSION, EnvVarConfig, PluginSchema
from atk.setup import mask_value, prompt_env_var, run_setup


class TestMaskValue:
    """Tests for mask_value function."""

    def test_masks_long_value_showing_last_4_chars(self) -> None:
        """Verify long values show asterisks with last 4 characters visible."""
        # Given
        value = "sk-1234567890abcdef"
        expected = "*" * (len(value) - 4) + "cdef"

        # When
        result = mask_value(value)

        # Then
        assert result == expected

    def test_masks_short_value_completely(self) -> None:
        """Verify short values (4 chars or less) are fully masked."""
        # Given
        value = "abc"
        expected = "***"

        # When
        result = mask_value(value)

        # Then
        assert result == expected

    def test_masks_exactly_4_chars_completely(self) -> None:
        """Verify 4-char values are fully masked."""
        # Given
        value = "abcd"
        expected = "****"

        # When
        result = mask_value(value)

        # Then
        assert result == expected


class TestPromptEnvVar:
    """Tests for prompt_env_var function."""

    def test_returns_user_input(self) -> None:
        """Verify user input is returned."""
        # Given
        var = EnvVarConfig(name="API_KEY")
        user_input = "my-api-key"
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return user_input

        # When
        result = prompt_env_var(var, None, mock_prompt)

        # Then
        assert result == user_input
        assert "API_KEY" in prompts_received[0]

    def test_returns_current_value_on_empty_input(self) -> None:
        """Verify pressing Enter returns current value."""
        # Given
        var = EnvVarConfig(name="API_KEY")
        current_value = "existing-key"

        def mock_prompt(_text: str) -> str:
            return ""

        # When
        result = prompt_env_var(var, current_value, mock_prompt)

        # Then
        assert result == current_value

    def test_returns_default_on_empty_input_when_no_current(self) -> None:
        """Verify pressing Enter returns default when no current value."""
        # Given
        default_value = "default-key"
        var = EnvVarConfig(name="API_KEY", default=default_value)

        def mock_prompt(_text: str) -> str:
            return ""

        # When
        result = prompt_env_var(var, None, mock_prompt)

        # Then
        assert result == default_value

    def test_shows_masked_current_value_for_secrets(self) -> None:
        """Verify secret values are masked in prompt."""
        # Given
        var = EnvVarConfig(name="SECRET_KEY", secret=True)
        current_value = "super-secret-value"
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return ""

        # When
        prompt_env_var(var, current_value, mock_prompt)

        # Then
        prompt_text = prompts_received[0]
        assert "super-secret-value" not in prompt_text
        assert "alue" in prompt_text  # Last 4 chars visible

    def test_shows_unmasked_current_value_for_non_secrets(self) -> None:
        """Verify non-secret values are shown in full."""
        # Given
        var = EnvVarConfig(name="DEBUG_MODE", secret=False)
        current_value = "true"
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return ""

        # When
        prompt_env_var(var, current_value, mock_prompt)

        # Then
        prompt_text = prompts_received[0]
        assert "true" in prompt_text

    def test_shows_default_value_in_prompt(self) -> None:
        """Verify default value is shown in prompt."""
        # Given
        default_value = "localhost:8080"
        var = EnvVarConfig(name="API_URL", default=default_value)
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return ""

        # When
        prompt_env_var(var, None, mock_prompt)

        # Then
        prompt_text = prompts_received[0]
        assert default_value in prompt_text

    def test_shows_required_indicator(self) -> None:
        """Verify required vars show (required) in prompt."""
        # Given
        var = EnvVarConfig(name="API_KEY", required=True)
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return "value"

        # When
        prompt_env_var(var, None, mock_prompt)

        # Then
        prompt_text = prompts_received[0]
        assert "(required)" in prompt_text

    def test_shows_description_in_prompt(self) -> None:
        """Verify description is shown in prompt."""
        # Given
        description = "Your OpenAI API key"
        var = EnvVarConfig(name="OPENAI_API_KEY", description=description)
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return "value"

        # When
        prompt_env_var(var, None, mock_prompt)

        # Then
        prompt_text = prompts_received[0]
        assert description in prompt_text


class TestRunSetup:
    """Tests for the run_setup function."""

    def test_merges_new_var_with_existing_env_file(self, tmp_path: Path) -> None:
        """run_setup must preserve vars already in .env that are not in the schema.

        This is the unit-level guard for Bug 2: during upgrade, run_setup is called
        with a filtered schema containing only NEW env vars. The existing vars in
        .env must survive — run_setup must not overwrite the file with only the
        newly-prompted vars.
        """
        # Given — .env already has a configured var from a previous setup
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        existing_token = "sk-existingsecret"
        env_file = plugin_dir / ".env"
        env_file.write_text(f"EXISTING_TOKEN={existing_token}\n")

        # Schema only contains the NEW var (simulating the filtered schema passed
        # by upgrade_plugin when it detects a newly-added env var)
        new_var_name = "NEW_API_KEY"
        new_var_value = "new-value-789"
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="Test Plugin",
            description="A plugin",
            env_vars=[EnvVarConfig(name=new_var_name, required=True)],
        )

        def capturing_prompt(text: str) -> str:
            return new_var_value if new_var_name in text else ""

        # When
        run_setup(plugin, plugin_dir, capturing_prompt)

        # Then — both the pre-existing and newly-prompted vars are in .env
        env_content = env_file.read_text()
        assert f"EXISTING_TOKEN={existing_token}" in env_content, (
            f"Existing var was lost. .env contents:\n{env_content}"
        )
        assert f"{new_var_name}={new_var_value}" in env_content, (
            f"New var not written. .env contents:\n{env_content}"
        )

