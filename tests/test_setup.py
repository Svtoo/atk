"""Tests for setup wizard functionality."""

from pathlib import Path

import pytest
import yaml

from atk.plugin_schema import EnvVarConfig, PLUGIN_SCHEMA_VERSION
from atk.setup import mask_value, prompt_env_var, run_setup


class TestMaskValue:
    """Tests for mask_value function."""

    def test_masks_long_value_showing_last_4_chars(self) -> None:
        """Verify long values show asterisks with last 4 characters visible."""
        value = "sk-1234567890abcdef"
        expected = "*" * (len(value) - 4) + "cdef"

        result = mask_value(value)

        assert result == expected

    def test_masks_short_value_completely(self) -> None:
        """Verify short values (4 chars or less) are fully masked."""
        value = "abc"
        expected = "***"

        result = mask_value(value)

        assert result == expected

    def test_masks_exactly_4_chars_completely(self) -> None:
        """Verify 4-char values are fully masked."""
        value = "abcd"
        expected = "****"

        result = mask_value(value)

        assert result == expected


class TestPromptEnvVar:
    """Tests for prompt_env_var function."""

    def test_returns_user_input(self) -> None:
        """Verify user input is returned."""
        var = EnvVarConfig(name="API_KEY")
        user_input = "my-api-key"
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return user_input

        result = prompt_env_var(var, None, mock_prompt)

        assert result == user_input
        assert "API_KEY" in prompts_received[0]

    def test_returns_current_value_on_empty_input(self) -> None:
        """Verify pressing Enter returns current value."""
        var = EnvVarConfig(name="API_KEY")
        current_value = "existing-key"

        def mock_prompt(text: str) -> str:
            return ""

        result = prompt_env_var(var, current_value, mock_prompt)

        assert result == current_value

    def test_returns_default_on_empty_input_when_no_current(self) -> None:
        """Verify pressing Enter returns default when no current value."""
        default_value = "default-key"
        var = EnvVarConfig(name="API_KEY", default=default_value)

        def mock_prompt(text: str) -> str:
            return ""

        result = prompt_env_var(var, None, mock_prompt)

        assert result == default_value

    def test_shows_masked_current_value_for_secrets(self) -> None:
        """Verify secret values are masked in prompt."""
        var = EnvVarConfig(name="SECRET_KEY", secret=True)
        current_value = "super-secret-value"
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return ""

        prompt_env_var(var, current_value, mock_prompt)

        prompt_text = prompts_received[0]
        assert "super-secret-value" not in prompt_text
        assert "alue" in prompt_text  # Last 4 chars visible

    def test_shows_unmasked_current_value_for_non_secrets(self) -> None:
        """Verify non-secret values are shown in full."""
        var = EnvVarConfig(name="DEBUG_MODE", secret=False)
        current_value = "true"
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return ""

        prompt_env_var(var, current_value, mock_prompt)

        prompt_text = prompts_received[0]
        assert "true" in prompt_text

    def test_shows_default_value_in_prompt(self) -> None:
        """Verify default value is shown in prompt."""
        default_value = "localhost:8080"
        var = EnvVarConfig(name="API_URL", default=default_value)
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return ""

        prompt_env_var(var, None, mock_prompt)

        prompt_text = prompts_received[0]
        assert default_value in prompt_text

    def test_shows_required_indicator(self) -> None:
        """Verify required vars show (required) in prompt."""
        var = EnvVarConfig(name="API_KEY", required=True)
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return "value"

        prompt_env_var(var, None, mock_prompt)

        prompt_text = prompts_received[0]
        assert "(required)" in prompt_text

    def test_shows_description_in_prompt(self) -> None:
        """Verify description is shown in prompt."""
        description = "Your OpenAI API key"
        var = EnvVarConfig(name="OPENAI_API_KEY", description=description)
        prompts_received: list[str] = []

        def mock_prompt(text: str) -> str:
            prompts_received.append(text)
            return "value"

        prompt_env_var(var, None, mock_prompt)

        prompt_text = prompts_received[0]
        assert description in prompt_text

