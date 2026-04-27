"""Tests for Phase 4 Core Setup Engine components."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from core.setup.host_executor import CommandResult, HostExecutor


@pytest.fixture
def mock_executor():
    with patch(
        "core.setup.host_executor.HostExecutor.run_async", new_callable=AsyncMock
    ) as m_async:
        yield m_async


def test_host_executor_prepare():
    executor = HostExecutor()
    executor.is_flatpak = True
    executor.has_pkexec = True
    executor.has_sudo = True

    cmd = ["git", "clone", "url"]
    prepared = executor._prepare_command(cmd, root=False)
    assert prepared == ["flatpak-spawn", "--host", "git", "clone", "url"]

    prepared_root = executor._prepare_command(cmd, root=True)
    assert prepared_root == ["flatpak-spawn", "--host", "pkexec", "git", "clone", "url"]

    executor.is_flatpak = False
    prepared = executor._prepare_command(cmd, root=False)
    assert prepared == ["git", "clone", "url"]
    prepared_root = executor._prepare_command(cmd, root=True)
    assert prepared_root == ["pkexec", "git", "clone", "url"]


def test_host_executor_fs_type(mock_executor):
    m_async = mock_executor
    # Mock df -T output (Header + Data)
    mock_out = "Filesystem     Type  1K-blocks  Used Available Use% Mounted on\n/dev/sda1      btrfs  10485760 1024 10484736   1% /"
    m_async.return_value = CommandResult(stdout=mock_out, stderr="", returncode=0, command=[])

    executor = HostExecutor()

    async def _run():
        return await executor.get_fs_type("/home")

    fs_type = asyncio.run(_run())
    assert fs_type == "btrfs"
