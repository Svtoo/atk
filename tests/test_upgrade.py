"""Tests for atk upgrade command."""

import os
import subprocess
from pathlib import Path
from typing import NamedTuple

import pytest
import yaml

from atk.add import add_plugin
from atk.init import init_atk_home
from atk.manifest_schema import PluginEntry, SourceInfo, SourceType, load_manifest, save_manifest
from atk.plugin_schema import PLUGIN_SCHEMA_VERSION
from atk.upgrade import LocalPluginError, UpgradeError, upgrade_plugin
from tests.conftest import (
    create_fake_git_repo,
    create_fake_registry,
    git_commit_all,
    noop_prompt,
)


class _GitPluginFixture(NamedTuple):
    """Everything needed to test upgrade on a git plugin."""

    atk_home: Path
    plugin_dir: Path
    repo_work_dir: Path
    repo_url: str
    original_ref: str
    plugin_identifier: str


def _setup_git_plugin(tmp_path: Path) -> _GitPluginFixture:
    """Create a fake git repo, add the plugin to ATK home, return fixture.

    Baseline plugin contains:
      - plugin.yaml  (name="Echo Tool", description="A test plugin from git")
      - install.sh   (a simple bash script)
    """
    atk_home = tmp_path / "atk-home"
    init_atk_home(atk_home)
    repo = create_fake_git_repo(tmp_path)
    add_plugin(repo.url, atk_home, noop_prompt)
    plugin_identifier = "echo-tool"
    plugin_dir = atk_home / "plugins" / plugin_identifier
    repo_work_dir = Path(repo.url.removeprefix("file://"))
    return _GitPluginFixture(
        atk_home=atk_home,
        plugin_dir=plugin_dir,
        repo_work_dir=repo_work_dir,
        repo_url=repo.url,
        original_ref=repo.commit_hash,
        plugin_identifier=plugin_identifier,
    )


class TestUpgradeRegistryPlugin:
    """Tests for upgrading registry plugins — verifies content, not just refs."""

    def test_upgrade_picks_up_changed_content(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Upgrade replaces on-disk plugin files with the new registry version."""
        # Given — add a registry plugin
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        registry = create_fake_registry(tmp_path)
        monkeypatch.setattr("atk.registry.REGISTRY_URL", registry.url)
        plugin_name = "test-plugin"
        add_plugin(plugin_name, atk_home, noop_prompt)
        plugin_dir = atk_home / "plugins" / plugin_name
        original_description = "A test plugin from registry"
        assert yaml.safe_load((plugin_dir / "plugin.yaml").read_text())["description"] == original_description

        # When — change description in registry and upgrade
        new_description = "Registry plugin v2 with improvements"
        registry_work_dir = Path(registry.url.removeprefix("file://"))
        plugin_yaml = registry_work_dir / "plugins" / "test-plugin" / "plugin.yaml"
        data = yaml.safe_load(plugin_yaml.read_text())
        data["description"] = new_description
        plugin_yaml.write_text(yaml.dump(data))
        git_commit_all(registry_work_dir, "Update plugin description")

        result = upgrade_plugin(plugin_name, atk_home, noop_prompt)

        # Then — on-disk file has the new content
        assert result.upgraded is True
        actual = yaml.safe_load((plugin_dir / "plugin.yaml").read_text())
        assert actual["description"] == new_description

    def test_already_up_to_date(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No remote changes means not upgraded."""
        # Given — add a registry plugin, no new commits
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        registry = create_fake_registry(tmp_path)
        monkeypatch.setattr("atk.registry.REGISTRY_URL", registry.url)
        plugin_name = "test-plugin"
        add_plugin(plugin_name, atk_home, noop_prompt)

        # When
        result = upgrade_plugin(plugin_name, atk_home, noop_prompt)

        # Then
        assert result.upgraded is False


class TestUpgradeGitPlugin:
    """Tests for upgrading git plugins — verifies actual on-disk content changes."""

    def test_upgrade_picks_up_changed_file_content(self, tmp_path: Path) -> None:
        """Upgrade replaces on-disk plugin.yaml with the new version's content."""
        # Given — baseline plugin
        fix = _setup_git_plugin(tmp_path)
        original_description = "A test plugin from git"
        assert yaml.safe_load((fix.plugin_dir / "plugin.yaml").read_text())["description"] == original_description

        # When — change description in remote and upgrade
        new_description = "Upgraded description with new features"
        plugin_yaml = fix.repo_work_dir / ".atk" / "plugin.yaml"
        data = yaml.safe_load(plugin_yaml.read_text())
        data["description"] = new_description
        plugin_yaml.write_text(yaml.dump(data))
        git_commit_all(fix.repo_work_dir, "Change description")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — on-disk file has the new content
        assert result.upgraded is True
        actual = yaml.safe_load((fix.plugin_dir / "plugin.yaml").read_text())
        assert actual["description"] == new_description

        # And — git log shows a commit for upgrading the plugin
        git_result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=fix.atk_home,
            capture_output=True,
            text=True,
            check=True,
        )
        assert "Upgrade plugin" in git_result.stdout

    def test_upgrade_picks_up_new_file(self, tmp_path: Path) -> None:
        """Upgrade adds files that were added in the new version."""
        # Given — baseline plugin (has plugin.yaml and install.sh)
        fix = _setup_git_plugin(tmp_path)
        new_file_name = "config.json"
        new_file_content = '{"setting": "value"}'
        assert not (fix.plugin_dir / new_file_name).exists()

        # When — add a new file in remote and upgrade
        (fix.repo_work_dir / ".atk" / new_file_name).write_text(new_file_content)
        git_commit_all(fix.repo_work_dir, "Add config file")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — new file exists on disk with correct content
        assert result.upgraded is True
        actual_content = (fix.plugin_dir / new_file_name).read_text()
        assert actual_content == new_file_content

    def test_upgrade_removes_deleted_file(self, tmp_path: Path) -> None:
        """Upgrade removes files that were deleted in the new version."""
        # Given — baseline plugin has install.sh
        fix = _setup_git_plugin(tmp_path)
        deleted_file = "install.sh"
        assert (fix.plugin_dir / deleted_file).exists()

        # When — delete install.sh in remote, change plugin.yaml so content differs
        os.remove(fix.repo_work_dir / ".atk" / deleted_file)
        plugin_yaml = fix.repo_work_dir / ".atk" / "plugin.yaml"
        data = yaml.safe_load(plugin_yaml.read_text())
        data["description"] = "Version without install script"
        plugin_yaml.write_text(yaml.dump(data))
        git_commit_all(fix.repo_work_dir, "Remove install script")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — file no longer exists on disk
        assert result.upgraded is True
        assert not (fix.plugin_dir / deleted_file).exists()

    def test_upgrade_overwrites_modified_file(self, tmp_path: Path) -> None:
        """Upgrade replaces file content even for non-YAML files."""
        # Given — baseline install.sh content
        fix = _setup_git_plugin(tmp_path)
        original_content = (fix.plugin_dir / "install.sh").read_text()
        new_script_content = "#!/bin/bash\necho 'New install v2'\napt-get update\n"
        assert original_content != new_script_content

        # When — overwrite install.sh in remote and upgrade
        (fix.repo_work_dir / ".atk" / "install.sh").write_text(new_script_content)
        git_commit_all(fix.repo_work_dir, "Update install script")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — on-disk file has the new content
        assert result.upgraded is True
        assert (fix.plugin_dir / "install.sh").read_text() == new_script_content

    def test_repo_commit_outside_plugin_dir_means_not_upgraded(self, tmp_path: Path) -> None:
        """A commit that only changes files outside .atk/ does not trigger upgrade."""
        # Given — baseline plugin
        fix = _setup_git_plugin(tmp_path)
        original_plugin_yaml = (fix.plugin_dir / "plugin.yaml").read_text()
        original_install_sh = (fix.plugin_dir / "install.sh").read_text()

        # When — commit changes only to README (outside .atk/)
        (fix.repo_work_dir / "README.md").write_text("# Updated readme\nNew content.\n")
        git_commit_all(fix.repo_work_dir, "Update README only")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — not upgraded, on-disk content unchanged
        assert result.upgraded is False
        assert (fix.plugin_dir / "plugin.yaml").read_text() == original_plugin_yaml
        assert (fix.plugin_dir / "install.sh").read_text() == original_install_sh

    def test_upgrade_already_up_to_date(self, tmp_path: Path) -> None:
        """No remote changes at all means not upgraded."""
        # Given — baseline plugin, no new commits
        fix = _setup_git_plugin(tmp_path)

        # When
        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then
        assert result.upgraded is False
        assert result.old_ref == fix.original_ref
        assert result.new_ref == fix.original_ref

    def test_upgrade_preserves_custom_directory(self, tmp_path: Path) -> None:
        """User's custom/ directory survives plugin file replacement."""
        # Given — baseline plugin with a user-created custom/ directory
        fix = _setup_git_plugin(tmp_path)
        custom_dir = fix.plugin_dir / "custom"
        custom_dir.mkdir()
        custom_file = "my-config.yaml"
        custom_content = "user_setting: true"
        (custom_dir / custom_file).write_text(custom_content)

        # When — change plugin content in remote and upgrade
        plugin_yaml = fix.repo_work_dir / ".atk" / "plugin.yaml"
        data = yaml.safe_load(plugin_yaml.read_text())
        data["description"] = "Version 2 with breaking changes"
        plugin_yaml.write_text(yaml.dump(data))
        git_commit_all(fix.repo_work_dir, "Update plugin")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — plugin upgraded but custom/ preserved
        assert result.upgraded is True
        preserved = fix.plugin_dir / "custom" / custom_file
        assert preserved.exists()
        assert preserved.read_text() == custom_content

    def test_upgrade_detects_new_env_vars(self, tmp_path: Path) -> None:
        """Upgrade reports env vars that were added in the new version."""
        # Given — baseline plugin (no env vars)
        fix = _setup_git_plugin(tmp_path)

        # When — add an env var in the new version and upgrade
        new_env_var_name = "NEW_API_KEY"
        plugin_yaml = fix.repo_work_dir / ".atk" / "plugin.yaml"
        data = yaml.safe_load(plugin_yaml.read_text())
        data["env_vars"] = [{"name": new_env_var_name, "required": True}]
        data["description"] = "Updated with env var"
        plugin_yaml.write_text(yaml.dump(data))
        git_commit_all(fix.repo_work_dir, "Add env var")

        result = upgrade_plugin(fix.plugin_identifier, fix.atk_home, noop_prompt)

        # Then — upgrade happened and new env var detected
        assert result.upgraded is True
        assert result.new_env_vars == [new_env_var_name]


class TestUpgradeErrors:
    """Tests for upgrade error cases."""

    def test_upgrade_local_plugin_raises_error(
        self, tmp_path: Path,
    ) -> None:
        """Verify upgrading a local plugin raises LocalPluginError."""
        # Given - a local plugin in the manifest
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)
        plugin_dir = atk_home / "plugins" / "my-local"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "plugin.yaml").write_text(yaml.dump({
            "schema_version": PLUGIN_SCHEMA_VERSION,
            "name": "My Local Plugin",
            "description": "A local plugin",
        }))
        manifest = load_manifest(atk_home)
        manifest.plugins.append(PluginEntry(
            name="My Local Plugin",
            directory="my-local",
            source=SourceInfo(type=SourceType.LOCAL),
        ))
        save_manifest(manifest, atk_home)

        # When / Then
        with pytest.raises(LocalPluginError, match="local plugin"):
            upgrade_plugin("my-local", atk_home, noop_prompt)

    def test_upgrade_nonexistent_plugin_raises_error(
        self, tmp_path: Path,
    ) -> None:
        """Verify upgrading a plugin not in manifest raises UpgradeError."""
        # Given - an initialized ATK home with no plugins
        atk_home = tmp_path / "atk-home"
        init_atk_home(atk_home)

        # When / Then
        with pytest.raises(UpgradeError, match="not found"):
            upgrade_plugin("nonexistent", atk_home, noop_prompt)
