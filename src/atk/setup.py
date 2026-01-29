"""Setup wizard for configuring plugin environment variables."""

from dataclasses import dataclass
from pathlib import Path

from atk.env import load_env_file, save_env_file
from atk.plugin_schema import EnvVarConfig, PluginSchema


@dataclass
class SetupResult:
    """Result of running setup for a plugin."""

    plugin_name: str
    configured_vars: list[str]


def mask_value(value: str) -> str:
    """Mask a secret value for display.

    Shows last 4 characters if value is long enough, otherwise shows asterisks.
    """
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def prompt_env_var(
    var: EnvVarConfig,
    current_value: str | None,
    prompt_func: callable,
) -> str:
    """Prompt user for a single environment variable value.

    Args:
        var: The environment variable configuration.
        current_value: Current value from .env file or environment.
        prompt_func: Function to call for prompting (allows testing).

    Returns:
        The value entered by the user (or current/default if Enter pressed).
    """
    prompt_parts = [var.name]

    if var.required:
        prompt_parts.append("(required)")

    if var.description:
        prompt_parts.append(f"- {var.description}")

    prompt_text = " ".join(prompt_parts)

    default_display = None
    if current_value:
        if var.secret:
            default_display = mask_value(current_value)
        else:
            default_display = current_value
    elif var.default:
        default_display = var.default

    if default_display:
        prompt_text += f" [{default_display}]"

    prompt_text += ": "

    entered = prompt_func(prompt_text)

    if entered == "":
        if current_value:
            return current_value
        if var.default:
            return var.default
        return ""

    return entered


def run_setup(
    plugin: PluginSchema,
    plugin_dir: Path,
    prompt_func: callable,
) -> SetupResult:
    """Run interactive setup for a plugin.

    Args:
        plugin: The plugin schema.
        plugin_dir: Path to the plugin directory.
        prompt_func: Function to call for prompting (allows testing).

    Returns:
        SetupResult with list of configured variable names.
    """
    if not plugin.env_vars:
        return SetupResult(plugin_name=plugin.name, configured_vars=[])

    env_file = plugin_dir / ".env"
    current_env = load_env_file(env_file) if env_file.exists() else {}

    new_env: dict[str, str] = {}
    descriptions: dict[str, str] = {}
    configured: list[str] = []

    for var in plugin.env_vars:
        current_value = current_env.get(var.name)
        value = prompt_env_var(var, current_value, prompt_func)
        if value:
            new_env[var.name] = value
            configured.append(var.name)
            if var.description:
                descriptions[var.name] = var.description

    if new_env:
        save_env_file(env_file, new_env, descriptions)

    return SetupResult(plugin_name=plugin.name, configured_vars=configured)

