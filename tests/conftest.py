"""Shared test fixtures for ATK tests."""

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest
import yaml
from typer.testing import CliRunner

from atk.init import init_atk_home
from atk.manifest_schema import PluginEntry, load_manifest, save_manifest
from atk.plugin_schema import (
    PLUGIN_SCHEMA_VERSION,
    EnvVarConfig,
    LifecycleConfig,
    McpConfig,
    PluginSchema,
    PortConfig,
)

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@test.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@test.com",
}


def noop_prompt(_text: str) -> str:
    """No-op prompt function for tests that don't need env var input."""
    return ""


def git_commit_all(work_dir: Path, message: str) -> str:
    """Stage all changes, commit, and return the new commit hash.

    Uses GIT_ENV for deterministic author/committer identity.
    """
    subprocess.run(["git", "add", "-A"], cwd=work_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=work_dir, check=True, capture_output=True, env=GIT_ENV,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=work_dir, check=True, capture_output=True, text=True,
    ).stdout.strip()


def serialize_plugin(plugin: PluginSchema) -> str:
    """Serialize a PluginSchema to YAML string.

    Helper function for tests that need to write plugin.yaml files manually.
    """
    return yaml.dump(plugin.model_dump(exclude_none=True), default_flow_style=False)


def write_plugin_yaml(path: Path, plugin: PluginSchema) -> None:
    """Write a PluginSchema to a plugin.yaml file.

    Combines serialization and file writing in one operation.

    Args:
        path: Path to the plugin.yaml file (or directory containing it)
        plugin: PluginSchema instance to serialize and write
    """
    # If path is a directory, append plugin.yaml
    if path.is_dir():
        path = path / "plugin.yaml"
    path.write_text(serialize_plugin(plugin))


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
PluginFactory = Callable[..., Path]


@pytest.fixture
def create_plugin(atk_home: Path) -> PluginFactory:
    """Factory fixture that returns a function to create plugins.

    Supports two calling patterns:

    1. New pattern (preferred) - Pass a PluginSchema instance:
        plugin = PluginSchema(
            schema_version=PLUGIN_SCHEMA_VERSION,
            name="MyPlugin",
            description="Test plugin",
            lifecycle=LifecycleConfig(start="echo hi"),
        )
        plugin_dir = create_plugin(plugin=plugin, directory="my-plugin")

    2. Legacy pattern (backward compatible) - Pass individual parameters:
        plugin_dir = create_plugin(
            "MyPlugin",
            "my-plugin",
            lifecycle=LifecycleConfig(start="echo hi"),
        )

    The directory parameter is required in both patterns.
    """

    def _create(
        name: str | None = None,
        directory: str | None = None,
        lifecycle: LifecycleConfig | dict | None = None,
        ports: list[PortConfig] | None = None,
        env_vars: list[EnvVarConfig] | None = None,
        mcp: McpConfig | None = None,
        *,
        plugin: PluginSchema | None = None,
    ) -> Path:
        # New pattern: plugin instance provided
        if plugin is not None:
            if directory is None:
                msg = "directory parameter is required when using plugin parameter"
                raise ValueError(msg)
            final_plugin = plugin
            final_directory = directory
        # Legacy pattern: individual parameters
        else:
            if name is None or directory is None:
                msg = "name and directory are required when not using plugin parameter"
                raise ValueError(msg)
            # Convert dict to LifecycleConfig if needed (for backward compatibility)
            if isinstance(lifecycle, dict):
                # Auto-add uninstall if install is present but uninstall is not
                # This ensures backward compatibility with tests that only specify install
                if "install" in lifecycle and "uninstall" not in lifecycle:
                    lifecycle["uninstall"] = "echo 'Auto-generated uninstall for testing'"
                lifecycle = LifecycleConfig.model_validate(lifecycle)
            final_plugin = PluginSchema(
                schema_version=PLUGIN_SCHEMA_VERSION,
                name=name,
                description=f"Test plugin {name}",
                lifecycle=lifecycle,
                ports=ports or [],
                env_vars=env_vars or [],
                mcp=mcp,
            )
            final_directory = directory

        plugin_dir = atk_home / "plugins" / final_directory
        plugin_dir.mkdir(parents=True, exist_ok=True)

        (plugin_dir / "plugin.yaml").write_text(
            yaml.dump(final_plugin.model_dump(exclude_none=True))
        )

        manifest = load_manifest(atk_home)
        manifest.plugins.append(
            PluginEntry(name=final_plugin.name, directory=final_directory)
        )
        save_manifest(manifest, atk_home)

        return plugin_dir

    return _create



class FakeRegistry(NamedTuple):
    """Result of creating a fake registry for testing."""

    url: str
    commit_hash: str


def create_fake_registry(tmp_path: Path) -> FakeRegistry:
    """Create a local git repo mimicking the atk-registry structure.

    Returns a FakeRegistry with the file:// URL and the commit hash.
    The repo contains a single plugin "test-plugin" with plugin.yaml
    and docker-compose.yml.
    """
    work_dir = tmp_path / "registry-work"
    work_dir.mkdir()
    plugins_dir = work_dir / "plugins" / "test-plugin"
    plugins_dir.mkdir(parents=True)

    (plugins_dir / "plugin.yaml").write_text(
        yaml.dump({
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": "Test Plugin",
            "description": "A test plugin from registry",
        })
    )
    (plugins_dir / "docker-compose.yml").write_text("version: '3'\n")

    (work_dir / "index.yaml").write_text(
        yaml.dump({
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "plugins": [
                {
                    "name": "test-plugin",
                    "path": "plugins/test-plugin",
                    "description": "A test plugin",
                }
            ],
        })
    )

    subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)
    commit_hash = git_commit_all(work_dir, "Initial")

    return FakeRegistry(url=f"file://{work_dir}", commit_hash=commit_hash)



class FakeGitRepo(NamedTuple):
    """Result of creating a fake git repo for testing."""

    url: str
    commit_hash: str


def create_fake_git_repo(
    tmp_path: Path,
    include_atk_dir: bool = True,
    include_plugin_yaml: bool = True,
) -> FakeGitRepo:
    """Create a local git repo mimicking a third-party repo with .atk/ dir.

    Args:
        tmp_path: Base temp directory.
        include_atk_dir: Whether to create the .atk/ directory.
        include_plugin_yaml: Whether to include plugin.yaml in .atk/.

    Returns:
        FakeGitRepo with file:// URL and commit hash.
    """
    work_dir = tmp_path / "fake-repo"
    work_dir.mkdir()

    # Always create a README so the repo has at least one file
    (work_dir / "README.md").write_text("# Fake repo\n")

    if include_atk_dir:
        atk_dir = work_dir / ".atk"
        atk_dir.mkdir()

        if include_plugin_yaml:
            plugin_data = {
                "schema_version": PLUGIN_SCHEMA_VERSION,
                "name": "Echo Tool",
                "description": "A test plugin from git",
            }
            (atk_dir / "plugin.yaml").write_text(yaml.dump(plugin_data))

        # Add a lifecycle script to verify all files are copied
        install_script = atk_dir / "install.sh"
        install_script.write_text("#!/bin/bash\necho 'Installing'\n")
        install_script.chmod(0o755)

    subprocess.run(["git", "init"], cwd=work_dir, check=True, capture_output=True)
    commit_hash = git_commit_all(work_dir, "Initial")

    return FakeGitRepo(url=f"file://{work_dir}", commit_hash=commit_hash)



def update_fake_repo(url: str, relative_path: str, message: str = "Update plugin") -> str:
    """Make a change to a file in a fake repo and commit it. Returns new commit hash.

    Modifies the 'description' field in the YAML file at relative_path
    to simulate a plugin update.

    Args:
        url: file:// URL of the repo.
        relative_path: Path to the YAML file within the repo (e.g. "plugins/test-plugin/plugin.yaml").
        message: Commit message.

    Returns:
        The new commit hash.
    """
    work_dir = Path(url.removeprefix("file://"))
    yaml_path = work_dir / relative_path
    data = yaml.safe_load(yaml_path.read_text())
    data["description"] = f"Updated — {message}"
    yaml_path.write_text(yaml.dump(data))
    return git_commit_all(work_dir, message)
