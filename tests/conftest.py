"""Shared test fixtures for ATK tests."""

from pathlib import Path
from typing import Callable

import pytest
import yaml
from typer.testing import CliRunner

from atk.init import init_atk_home
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture
def atk_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create and initialize an ATK home directory.

    Sets ATK_HOME environment variable and initializes the directory structure.
    Returns the path to the ATK home directory.
    """
    monkeypatch.setenv("ATK_HOME", str(tmp_path))
    init_atk_home(tmp_path)
    return tmp_path


# Type alias for the plugin factory function
PluginFactory = Callable[[str, str, dict[str, str] | None], Path]


@pytest.fixture
def create_plugin(atk_home: Path) -> PluginFactory:
    """Factory fixture that returns a function to create plugins.

    The fixture itself takes no arguments beyond the atk_home dependency.
    It returns a factory function with signature:
        (name: str, directory: str, lifecycle: dict | None) -> Path

    Usage:
        def test_something(create_plugin):
            plugin_dir = create_plugin("MyPlugin", "my-plugin", {"start": "echo hi"})
    """

    def _create(
        name: str,
        directory: str,
        lifecycle: dict[str, str] | None = None,
    ) -> Path:
        plugin_dir = atk_home / "plugins" / directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        plugin_yaml: dict = {
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": name,
            "description": f"Test plugin {name}",
        }
        if lifecycle:
            plugin_yaml["lifecycle"] = lifecycle

        (plugin_dir / "plugin.yaml").write_text(yaml.dump(plugin_yaml))

        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(name=name, directory=directory))
        save_manifest(manifest, atk_home)

        return plugin_dir

    return _create

