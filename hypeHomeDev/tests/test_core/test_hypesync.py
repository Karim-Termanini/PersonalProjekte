"""Tests for Agent C HypeSync components: SyncManager, DotfilesDriver, SecretsManager."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.setup.host_executor import CommandResult, HostExecutor
from core.setup.sync_manager import (
    DotfilesDriver,
    SecretConfig,
    SecretsManager,
    SyncManager,
)


@pytest.fixture
def mock_executor():
    """Create a mock HostExecutor."""
    executor = MagicMock(spec=HostExecutor)
    executor.run_async = AsyncMock()
    return executor


@pytest.fixture
def mock_git_ops():
    """Create a mock GitOperations."""
    git_ops = MagicMock()
    git_ops.clone = AsyncMock()
    return git_ops


@pytest.fixture
def dotfiles_driver(mock_executor, mock_git_ops):
    """Create a DotfilesDriver with mock dependencies."""
    return DotfilesDriver(mock_executor, mock_git_ops)


@pytest.fixture
def secrets_manager(mock_executor):
    """Create a SecretsManager with mock executor."""
    return SecretsManager(mock_executor)


@pytest.fixture
def sync_manager(mock_executor, mock_git_ops):
    """Create a SyncManager with mock dependencies."""
    return SyncManager(mock_executor, mock_git_ops)


# DotfilesDriver Tests


def test_apply_chezmoi_success(dotfiles_driver, mock_git_ops, tmp_path):
    """Test applying dotfiles with Chezmoi."""
    # Setup: .chezmoiroot exists
    (tmp_path / ".chezmoiroot").touch()

    # Mock git clone
    mock_git_ops.clone.return_value = True

    # Mock executor for chezmoi
    async def mock_run(cmd, root=False):
        if cmd[:2] == ["which", "chezmoi"]:
            return CommandResult("/usr/bin/chezmoi\n", "", 0, cmd)
        if cmd[0] == "chezmoi":
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    dotfiles_driver._executor.run_async.side_effect = mock_run

    async def _run():
        return await dotfiles_driver.apply(
            "https://github.com/user/dotfiles.git",
            tmp_path,
        )

    result = asyncio.run(_run())
    assert result is True


def test_apply_stow_success(dotfiles_driver, mock_git_ops, tmp_path):
    """Test applying dotfiles with GNU Stow."""
    # Setup: stow directory structure
    (tmp_path / "vim").mkdir()
    (tmp_path / "bash").mkdir()

    mock_git_ops.clone.return_value = True

    async def mock_run(cmd, root=False):
        if cmd[0] == "which":
            if "chezmoi" in cmd:
                return CommandResult("", "", 1, cmd)
            if "stow" in cmd:
                return CommandResult("/usr/bin/stow\n", "", 0, cmd)
        if cmd[0] == "stow":
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    dotfiles_driver._executor.run_async.side_effect = mock_run

    async def _run():
        return await dotfiles_driver.apply(
            "https://github.com/user/dotfiles.git",
            tmp_path,
        )

    result = asyncio.run(_run())
    assert result is True


def test_apply_custom_script_success(dotfiles_driver, mock_git_ops, tmp_path):
    """Test applying dotfiles with custom script."""
    # Setup: install.sh exists
    script_path = tmp_path / "install.sh"
    script_path.touch()

    mock_git_ops.clone.return_value = True

    async def mock_run(cmd, root=False, **kwargs):
        if cmd[0] == "which":
            return CommandResult("", "", 1, cmd)
        if cmd[0] in ["chmod", "bash"]:
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    dotfiles_driver._executor.run_async.side_effect = mock_run

    async def _run():
        return await dotfiles_driver.apply(
            "https://github.com/user/dotfiles.git",
            tmp_path,
        )

    result = asyncio.run(_run())
    assert result is True


def test_apply_dotfiles_clone_failure(dotfiles_driver, mock_git_ops, tmp_path):
    """Test failure when cloning dotfiles repo."""
    mock_git_ops.clone.return_value = False

    # Use a fresh subdirectory that definitely doesn't exist
    fresh_path = tmp_path / "fresh_dotfiles_test"

    async def mock_run(cmd, root=False):
        if cmd[0] == "which":
            return CommandResult("", "", 1, cmd)
        return CommandResult("", "", 0, cmd)

    dotfiles_driver._executor.run_async.side_effect = mock_run

    async def _run():
        return await dotfiles_driver.apply(
            "https://github.com/user/dotfiles.git",
            fresh_path,
        )

    result = asyncio.run(_run())
    assert result is False


# SecretsManager Tests


def test_bridge_ssh_agent(secrets_manager):
    """Test SSH agent bridging."""

    async def mock_run(cmd, root=False):
        return CommandResult("", "", 0, cmd)

    secrets_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await secrets_manager.bridge_ssh("test-container")

    result = asyncio.run(_run())
    assert result is True


def test_bridge_ssh_with_whitelist(secrets_manager):
    """Test SSH key bridging with whitelist."""
    config = SecretConfig(
        inject_ssh_keys=True,
        ssh_key_whitelist=["id_ed25519", "id_rsa"],
    )

    async def mock_run(cmd, root=False):
        return CommandResult("", "", 0, cmd)

    secrets_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await secrets_manager.bridge_ssh("test-container", config)

    result = asyncio.run(_run())
    assert result is True


def test_bridge_ssh_disabled(secrets_manager):
    """Test SSH bridging disabled by config."""
    config = SecretConfig(inject_ssh_keys=False)

    async def _run():
        return await secrets_manager.bridge_ssh("test-container", config)

    result = asyncio.run(_run())
    assert result is True


def test_bridge_git_config(secrets_manager):
    """Test Git config bridging."""

    async def mock_run(cmd, root=False):
        if cmd[:4] == ["git", "config", "--global", "user.name"]:
            return CommandResult("Test User\n", "", 0, cmd)
        if cmd[:4] == ["git", "config", "--global", "user.email"]:
            return CommandResult("test@example.com\n", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    secrets_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await secrets_manager.bridge_git_config("test-container")

    result = asyncio.run(_run())
    assert result is True


def test_bridge_git_config_disabled(secrets_manager):
    """Test Git config bridging disabled."""
    config = SecretConfig(inject_git_credentials=False)

    async def _run():
        return await secrets_manager.bridge_git_config("test-container", config)

    result = asyncio.run(_run())
    assert result is True


def test_bridge_tokens(secrets_manager):
    """Test token bridging."""
    config = SecretConfig(inject_github_token=True)

    async def mock_run(cmd, root=False):
        return CommandResult("", "", 0, cmd)

    secrets_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await secrets_manager.bridge_tokens("test-container", config)

    result = asyncio.run(_run())
    assert result is True


def test_bridge_tokens_disabled(secrets_manager):
    """Test token bridging disabled."""
    config = SecretConfig(inject_github_token=False)

    async def _run():
        return await secrets_manager.bridge_tokens("test-container", config)

    result = asyncio.run(_run())
    assert result is True


# SyncManager Integration Tests


def test_sync_manager_sync_dotfiles(sync_manager, mock_git_ops, tmp_path):
    """Test full dotfiles sync flow."""
    # Mock successful clone
    mock_git_ops.clone.return_value = True

    # Setup: .chezmoiroot exists in target
    (tmp_path / ".chezmoiroot").touch()

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["which", "chezmoi"]:
            return CommandResult("/usr/bin/chezmoi\n", "", 0, cmd)
        if cmd[0] == "chezmoi":
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    sync_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await sync_manager.sync_dotfiles(
            "https://github.com/user/dotfiles.git",
        )

    result = asyncio.run(_run())
    assert result is True


def test_sync_manager_inject_secrets(sync_manager):
    """Test full secret injection flow."""
    config = SecretConfig(
        inject_ssh_keys=True,
        inject_github_token=True,
        inject_git_credentials=True,
    )

    async def mock_run(cmd, root=False):
        return CommandResult("", "", 0, cmd)

    sync_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await sync_manager.inject_secrets(
            container_name="test-container",
            config=config,
        )

    result = asyncio.run(_run())
    assert result is True


def test_sync_manager_inject_secrets_host_only(sync_manager):
    """Test secret injection on host only (no container)."""

    async def mock_run(cmd, root=False):
        return CommandResult("", "", 0, cmd)

    sync_manager._executor.run_async.side_effect = mock_run

    async def _run():
        return await sync_manager.inject_secrets()

    result = asyncio.run(_run())
    assert result is True


# SecretConfig Tests


def test_secret_config_defaults():
    """Test SecretConfig default values."""
    config = SecretConfig()
    assert config.inject_ssh_keys is True
    assert config.inject_git_credentials is True
    assert config.inject_github_token is False
    assert "id_rsa" in config.ssh_key_whitelist
    assert "id_ed25519" in config.ssh_key_whitelist
    assert "GITHUB_TOKEN" in config.token_whitelist


def test_secret_config_custom():
    """Test SecretConfig with custom values."""
    config = SecretConfig(
        inject_ssh_keys=False,
        ssh_key_whitelist=["id_custom"],
        token_whitelist=["CUSTOM_TOKEN"],
    )
    assert config.inject_ssh_keys is False
    assert config.ssh_key_whitelist == ["id_custom"]
    assert config.token_whitelist == ["CUSTOM_TOKEN"]


# Edge Cases and Error Handling


def test_apply_dotfiles_no_manager(dotfiles_driver, mock_git_ops, tmp_path):
    """Test when no manager is found."""
    mock_git_ops.clone.return_value = True

    async def mock_run(cmd, root=False):
        if cmd[0] == "which":
            return CommandResult("", "", 1, cmd)
        return CommandResult("", "", 0, cmd)

    dotfiles_driver._executor.run_async.side_effect = mock_run

    async def _run():
        return await dotfiles_driver.apply(
            "https://github.com/user/dotfiles.git",
            tmp_path,
        )

    result = asyncio.run(_run())
    # Should still return True (graceful fallback)
    assert result is True


def test_sync_manager_full_flow(sync_manager, mock_git_ops, tmp_path):
    """Test full HypeSync flow: dotfiles + secrets."""
    # Setup dotfiles
    (tmp_path / ".chezmoiroot").touch()
    mock_git_ops.clone.return_value = True

    async def mock_run(cmd, root=False):
        if cmd[:2] == ["which", "chezmoi"]:
            return CommandResult("/usr/bin/chezmoi\n", "", 0, cmd)
        if cmd[0] in ["chezmoi", "distrobox", "git", "chmod", "bash"]:
            return CommandResult("", "", 0, cmd)
        return CommandResult("", "", 0, cmd)

    sync_manager._executor.run_async.side_effect = mock_run

    config = SecretConfig(
        inject_ssh_keys=True,
        inject_github_token=True,
        inject_git_credentials=True,
    )

    async def _run():
        # 1. Sync dotfiles to host
        dotfiles_ok = await sync_manager.sync_dotfiles("https://github.com/user/dotfiles.git")
        # 2. Inject secrets to container
        secrets_ok = await sync_manager.inject_secrets("test-container", config)
        return dotfiles_ok and secrets_ok

    result = asyncio.run(_run())
    assert result is True
