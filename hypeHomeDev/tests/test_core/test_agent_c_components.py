"""Tests for Agent C components: DevFolderCreator, DevSettingsApplier, ConfigBackupManager, Environments."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.setup.config_backup import (
    BackupMetadata,
    BackupResult,
    ConfigBackupManager,
)
from core.setup.dev_folder import DevFolderCreator
from core.setup.dev_settings import DevSettingsApplier, SettingsResult
from core.setup.environments import DevContainerConfig, EnvironmentManager
from core.setup.host_executor import CommandResult, HostExecutor


@pytest.fixture
def mock_executor():
    """Create a mock HostExecutor."""
    executor = MagicMock(spec=HostExecutor)
    executor.run_async = AsyncMock()
    executor.get_fs_type = AsyncMock()
    return executor


@pytest.fixture
def dev_folder_creator(mock_executor):
    """Create a DevFolderCreator with mock executor."""
    return DevFolderCreator(mock_executor)


@pytest.fixture
def dev_settings_applier(mock_executor):
    """Create a DevSettingsApplier with mock executor."""
    return DevSettingsApplier(mock_executor)


@pytest.fixture
def config_backup_manager(mock_executor):
    """Create a ConfigBackupManager with mock executor."""
    return ConfigBackupManager(mock_executor, backup_dir="/tmp/test_backups")


@pytest.fixture
def environment_manager(mock_executor):
    """Create an EnvironmentManager with mock executor."""
    return EnvironmentManager(mock_executor)


# DevFolderCreator Tests


def test_dev_folder_creator_create_success(mock_executor, dev_folder_creator):
    """Test successful dev folder creation."""

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["test", "-e"]:
            return CommandResult("", "", 1, cmd)  # Path doesn't exist
        if cmd[:3] == ["mkdir", "-p"]:
            return CommandResult("", "", 0, cmd)
        if cmd[0] == "chmod":
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run
    mock_executor.get_fs_type.return_value = "ext4"

    async def _run():
        return await dev_folder_creator.create_dev_folder("~/Dev", use_btrfs=False)

    result = asyncio.run(_run())
    assert result.success is True
    assert "Dev" in result.path


def test_dev_folder_creator_already_exists(mock_executor, dev_folder_creator):
    """Test when dev folder already exists."""

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["test", "-e"]:
            return CommandResult("", "", 0, cmd)  # Path exists
        if cmd[:2] == ["test", "-d"]:
            return CommandResult("", "", 0, cmd)  # Is directory
        if cmd[0] == "df":
            return CommandResult("/dev/sda1 ext4 100G 50G 50G 50% /home\n", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run
    mock_executor.get_fs_type.return_value = "ext4"

    async def _run():
        return await dev_folder_creator.create_dev_folder("~/Dev")

    result = asyncio.run(_run())
    assert result.success is True
    assert "already exists" in result.message


def test_dev_folder_creator_btrfs_subvolume(mock_executor, dev_folder_creator):
    """Test Btrfs subvolume creation."""

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["test", "-e"]:
            return CommandResult("", "", 1, cmd)
        if cmd[0] == "df":
            return CommandResult("/dev/sda1 btrfs 100G 50G 50G 50% /home\n", "", 0, cmd)
        if cmd[0] == "mkdir":
            return CommandResult("", "", 0, cmd)
        if cmd[:2] == ["btrfs", "subvolume"]:
            return CommandResult("", "", 0, cmd)
        if cmd[0] == "chmod":
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run
    mock_executor.get_fs_type.return_value = "btrfs"

    async def _run():
        return await dev_folder_creator.create_dev_folder("~/Dev", use_btrfs=True)

    result = asyncio.run(_run())
    assert result.success is True
    assert result.btrfs_optimized is True


def test_dev_folder_creator_create_nested(mock_executor, dev_folder_creator):
    """Test creating nested dev folders."""
    mock_executor.run_async.return_value = CommandResult("", "", 0, [])

    async def _run():
        return await dev_folder_creator.create_nested_folders("~/Dev")

    result = asyncio.run(_run())
    assert result is True
    assert mock_executor.run_async.call_count == 4  # projects, experiments, tools, docs


# DevSettingsApplier Tests


def test_dev_settings_applier_apply_all(mock_executor, dev_settings_applier):
    """Test applying all developer settings."""

    async def mock_run(cmd, root=False):
        # Simulate shell detection
        if "echo $SHELL" in " ".join(cmd):
            return CommandResult("/bin/bash\n", "", 0, cmd)
        # Simulate which commands for file manager
        if cmd[0] == "which":
            return CommandResult("", "", 1, cmd)  # No file manager found
        # Simulate grep checks
        if cmd[0] == "grep":
            return CommandResult("", "", 1, cmd)  # Marker not found
        # All other commands succeed
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        return await dev_settings_applier.apply_settings(
            git_name="Test User",
            git_email="test@example.com",
            git_editor="nvim",
            enable_aliases=True,
            enable_hidden_files=True,
            enable_file_extensions=True,
            enable_ssh_agent=True,
            env_vars={"EDITOR": "nvim"},
        )

    result = asyncio.run(_run())
    assert isinstance(result, SettingsResult)
    assert len(result.applied_settings) > 0


def test_dev_settings_applier_detect_shell_bash(mock_executor, dev_settings_applier):
    """Test shell detection for bash."""
    mock_executor.run_async.return_value = CommandResult("/bin/bash\n", "", 0, [])

    async def _run():
        await dev_settings_applier._detect_shell()
        return dev_settings_applier._detected_shell

    result = asyncio.run(_run())
    assert result == "bash"


def test_dev_settings_applier_detect_shell_zsh(mock_executor, dev_settings_applier):
    """Test shell detection for zsh."""
    mock_executor.run_async.return_value = CommandResult("/bin/zsh\n", "", 0, [])

    async def _run():
        await dev_settings_applier._detect_shell()
        return dev_settings_applier._detected_shell

    result = asyncio.run(_run())
    assert result == "zsh"


def test_dev_settings_applier_preview(mock_executor, dev_settings_applier):
    """Test previewing changes."""

    async def _run():
        return await dev_settings_applier.preview_changes()

    preview = asyncio.run(_run())
    assert "shell_aliases" in preview
    assert "ssh_agent" in preview
    assert "git_config" in preview
    assert "file_manager" in preview


# ConfigBackupManager Tests


def test_config_backup_manager_create_backup(mock_executor, config_backup_manager):
    """Test creating a backup."""
    call_count = 0

    async def mock_run(cmd, root=False):
        nonlocal call_count
        call_count += 1
        # Simulate most files don't exist
        if cmd[:2] == ["test", "-e"]:
            # Only backup some files
            path = cmd[2] if len(cmd) > 2 else ""
            if ".gitconfig" in path or ".bashrc" in path:
                return CommandResult("", "", 0, cmd)  # File exists
            return CommandResult("", "", 1, cmd)  # File doesn't exist
        if cmd[0] == "mkdir":
            return CommandResult("", "", 0, cmd)
        if cmd[0] == "cp":
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        return await config_backup_manager.create_backup(description="Test backup")

    result = asyncio.run(_run())
    assert isinstance(result, BackupResult)
    assert result.success is True
    assert result.metadata is not None
    assert result.metadata.description == "Test backup"


def test_config_backup_manager_list_backups(mock_executor, config_backup_manager):
    """Test listing backups."""

    async def mock_run(cmd, root=False):
        if cmd[0] == "find":
            # Return mock backup directories
            return CommandResult(
                "/tmp/test_backups/backup_20260414_120000\n/tmp/test_backups/backup_20260414_130000\n",
                "",
                0,
                cmd,
            )
        if cmd[:2] == ["test", "-e"]:
            return CommandResult("", "", 0, cmd)
        if cmd[0] == "cat":
            # Return mock metadata
            metadata = {
                "timestamp": "20260414_130000",
                "backup_id": "backup_20260414_130000",
                "files": ["~/.gitconfig", "~/.bashrc"],
                "description": "Test backup",
                "success": True,
                "error": "",
            }
            return CommandResult(json.dumps(metadata), "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        return await config_backup_manager.list_backups()

    backups = asyncio.run(_run())
    assert isinstance(backups, list)
    assert len(backups) > 0


def test_config_backup_manager_get_latest_backup(mock_executor, config_backup_manager):
    """Test getting the latest backup."""
    # Mock list_backups to return some backups
    with patch.object(
        config_backup_manager,
        "list_backups",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = [
            BackupMetadata(
                timestamp="20260414_130000",
                backup_id="backup_20260414_130000",
                files=["~/.gitconfig"],
            ),
            BackupMetadata(
                timestamp="20260414_120000",
                backup_id="backup_20260414_120000",
                files=["~/.bashrc"],
            ),
        ]

        async def _run():
            return await config_backup_manager.get_latest_backup()

        latest = asyncio.run(_run())
        assert latest is not None
        assert latest.backup_id == "backup_20260414_130000"


def test_config_backup_manager_delete_backup(mock_executor, config_backup_manager):
    """Test deleting a backup."""
    mock_executor.run_async.return_value = CommandResult("", "", 0, [])

    async def _run():
        return await config_backup_manager.delete_backup("backup_20260414_120000")

    result = asyncio.run(_run())
    assert result is True


def test_config_backup_manager_cleanup_old_backups(mock_executor, config_backup_manager):
    """Test cleaning up old backups."""
    # Mock list_backups to return many backups
    with patch.object(
        config_backup_manager,
        "list_backups",
        new_callable=AsyncMock,
    ) as mock_list:
        mock_list.return_value = [
            BackupMetadata(
                timestamp=f"20260414_{120000 + i}",
                backup_id=f"backup_20260414_{120000 + i}",
                files=["~/.gitconfig"],
            )
            for i in range(10)
        ]

        # Mock delete_backup
        with patch.object(
            config_backup_manager,
            "delete_backup",
            new_callable=AsyncMock,
        ) as mock_delete:
            mock_delete.return_value = True

            async def _run():
                return await config_backup_manager.cleanup_old_backups(keep_count=5)

            deleted = asyncio.run(_run())
            assert deleted == 5  # Should delete 5 oldest backups


# EnvironmentManager Tests


def test_environment_manager_initialize(mock_executor, environment_manager):
    """Test initializing environment manager."""

    async def mock_run(cmd, root=False):
        # Simulate distrobox and podman available
        if cmd == ["which", "distrobox"]:
            return CommandResult("/usr/bin/distrobox\n", "", 0, cmd)
        if cmd == ["which", "podman"]:
            return CommandResult("/usr/bin/podman\n", "", 0, cmd)
        return CommandResult("", "", 1, cmd)  # Others not found

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        await environment_manager.initialize()
        return (
            environment_manager.has_distrobox,
            environment_manager.has_toolbx,
            environment_manager.has_podman,
            environment_manager.has_docker,
        )

    result = asyncio.run(_run())
    assert result == (True, False, True, False)


def test_environment_manager_create_distrobox(mock_executor, environment_manager):
    """Test creating a Distrobox container."""
    environment_manager.has_distrobox = True
    mock_executor.run_async.return_value = CommandResult("", "", 0, [])

    async def _run():
        return await environment_manager.create_distrobox("testbox", "ubuntu:latest")

    result = asyncio.run(_run())
    assert result is True


def test_environment_manager_generate_devcontainer_config(environment_manager):
    """Test generating devcontainer configuration."""

    async def _run():
        config = await environment_manager.generate_devcontainer_config(
            "/workspace",
            image="mcr.microsoft.com/devcontainers/python:3",
            extensions=["ms-python.python"],
        )
        return config

    config = asyncio.run(_run())
    assert isinstance(config, DevContainerConfig)
    assert config.name == "HypeDevHome DevContainer"
    assert config.image == "mcr.microsoft.com/devcontainers/python:3"
    assert "ms-python.python" in config.extensions


def test_environment_manager_create_devcontainer(mock_executor, environment_manager):
    """Test creating a devcontainer."""
    config = DevContainerConfig(
        name="Test Container",
        image="ubuntu:latest",
        workspace_folder="/workspace",
        extensions=["ms-python.python"],
    )

    mock_executor.run_async.return_value = CommandResult("", "", 0, [])

    async def _run():
        return await environment_manager.create_devcontainer("/workspace", config)

    result = asyncio.run(_run())
    assert result is True


def test_environment_manager_detect_devcontainer(mock_executor, environment_manager):
    """Test detecting devcontainer configuration."""

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["test", "-f"]:
            if "devcontainer.json" in cmd[-1]:
                return CommandResult("", "", 0, cmd)  # File exists
            return CommandResult("", "", 1, cmd)  # File doesn't exist
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        return await environment_manager.detect_devcontainer("/workspace")

    result = asyncio.run(_run())
    assert result is True


def test_environment_manager_get_cloud_environments(environment_manager):
    """Test getting cloud environment placeholders."""
    cloud_envs = environment_manager.get_cloud_environments()
    assert len(cloud_envs) == 3
    assert cloud_envs[0].name == "GitHub Codespaces"
    assert cloud_envs[1].name == "Gitpod"
    assert cloud_envs[2].name == "AWS Cloud9"
    assert all(env.coming_soon for env in cloud_envs)


def test_environment_manager_get_container_tools(environment_manager):
    """Test getting container tools availability."""
    environment_manager.has_distrobox = True
    environment_manager.has_podman = True

    tools = environment_manager.get_container_tools()
    assert tools["distrobox"] is True
    assert tools["podman"] is True
    assert tools["docker"] is False


def test_environment_manager_create_toolbox(mock_executor, environment_manager):
    """Test creating a Toolbx container."""
    environment_manager.has_toolbx = True
    mock_executor.run_async.return_value = CommandResult("", "", 0, [])

    async def _run():
        return await environment_manager.create_toolbox("devbox")

    result = asyncio.run(_run())
    assert result is True


# Integration Tests


def test_dev_folder_and_settings_integration(mock_executor):
    """Test integration of dev folder creation and settings application."""
    from core.setup.dev_folder import DevFolderCreator
    from core.setup.dev_settings import DevSettingsApplier

    dev_folder_creator = DevFolderCreator(mock_executor)
    dev_settings_applier = DevSettingsApplier(mock_executor)

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["test", "-e"]:
            return CommandResult("", "", 1, cmd)
        if cmd[0] == "which":
            return CommandResult("", "", 1, cmd)
        if "echo $SHELL" in " ".join(cmd):
            return CommandResult("/bin/bash\n", "", 0, cmd)
        if cmd[0] == "grep":
            return CommandResult("", "", 1, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        folder_result = await dev_folder_creator.create_dev_folder("~/Dev")
        settings_result = await dev_settings_applier.apply_settings(
            git_name="Test User",
            git_email="test@example.com",
        )
        return folder_result, settings_result

    folder_result, settings_result = asyncio.run(_run())
    assert folder_result.success is True
    assert isinstance(settings_result, SettingsResult)


def test_backup_and_restore_integration(mock_executor):
    """Test integration of backup and restore operations."""
    config_backup_manager = ConfigBackupManager(mock_executor)

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["test", "-e"]:
            # Simulate some files exist
            path = cmd[2] if len(cmd) > 2 else ""
            if ".gitconfig" in path:
                return CommandResult("", "", 0, cmd)
            return CommandResult("", "", 1, cmd)
        if cmd[0] in ["mkdir", "cp", "cat", "rm", "tar"]:
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    async def _run():
        # Create backup
        backup_result = await config_backup_manager.create_backup("Test")
        assert backup_result.success is True

        # List backups
        backups = await config_backup_manager.list_backups()

        # Get latest
        latest = await config_backup_manager.get_latest_backup()

        return backup_result, backups, latest

    backup_result, backups, _latest = asyncio.run(_run())
    assert backup_result.success is True
    assert isinstance(backups, list)
