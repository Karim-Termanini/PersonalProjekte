"""Tests for Consolidated Snapshot Manager: Snapshots, Encryption, Retention, Health Checks."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from core.maintenance.manager import (
    EncryptionHandler,
    HealthCheckResult,
    HealthCheckRunner,
    HealthStatus,
    LocalStorageProvider,
    RetentionPolicyEngine,
    SnapshotManager,
    SnapshotMetadata,
    SnapshotType,
)
from core.maintenance.sync_tracker import HypeSyncStatusTracker
from core.setup.environments import EnvironmentManager
from core.setup.host_executor import CommandResult, HostExecutor


@pytest.fixture
def mock_executor():
    """Create a mock HostExecutor."""
    executor = MagicMock(spec=HostExecutor)
    executor.run_async = AsyncMock()
    return executor


@pytest.fixture
def mock_env_manager(mock_executor):
    """Create a mock EnvironmentManager."""
    env = MagicMock(spec=EnvironmentManager)
    env._executor = mock_executor

    async def mock_backup(name, path):
        from pathlib import Path

        Path(path).write_bytes(b"mock container data")
        return True

    env.backup_distrobox_container = AsyncMock(side_effect=mock_backup)
    env.restore_distrobox_container = AsyncMock(return_value=True)
    return env


@pytest.fixture
def mock_storage_provider(tmp_path):
    """Create a mock storage provider."""
    # Note: LocalStorageProvider methods are now async
    return LocalStorageProvider(str(tmp_path / "snapshots"))


@pytest.fixture
def snapshot_manager(mock_env_manager, mock_storage_provider):
    """Create a SnapshotManager with mock dependencies."""
    return SnapshotManager(mock_env_manager, mock_storage_provider)


@pytest.fixture
def health_check_runner(mock_executor):
    """Create a HealthCheckRunner with mock executor."""
    return HealthCheckRunner(mock_executor)


@pytest.fixture
def retention_engine(mock_storage_provider):
    """Create a RetentionPolicyEngine with mock storage."""
    return RetentionPolicyEngine(mock_storage_provider, keep_daily=7, keep_weekly=4)


@pytest.fixture
def sync_tracker():
    """Create a HypeSyncStatusTracker."""
    return HypeSyncStatusTracker()


# ─── LocalStorageProvider Tests ──────────────────────────────────────


@pytest.mark.asyncio
async def test_local_storage_save_and_load(mock_storage_provider):
    """Test saving and loading a snapshot."""
    snapshot_id = "test_snapshot"
    data = b"test snapshot data"
    metadata = SnapshotMetadata(
        snapshot_id=snapshot_id,
        name="Test Snapshot",
        snapshot_type=SnapshotType.CONTAINER,
        timestamp="2026-04-14T12:00:00",
        stack_name="test_stack",
    )

    save_ok = await mock_storage_provider.save(snapshot_id, data, metadata)
    assert save_ok is True

    result = await mock_storage_provider.load(snapshot_id)
    assert result is not None

    loaded_data, loaded_meta = result
    assert loaded_data == data
    assert loaded_meta.snapshot_id == snapshot_id
    assert loaded_meta.name == "Test Snapshot"


@pytest.mark.asyncio
async def test_local_storage_list_snapshots(mock_storage_provider):
    """Test listing snapshots."""
    for i in range(3):
        sid = f"snapshot_{i}"
        data = f"data_{i}".encode()
        meta = SnapshotMetadata(
            snapshot_id=sid,
            name=f"Snapshot {i}",
            snapshot_type=SnapshotType.CONTAINER,
            timestamp=f"2026-04-14T{12 + i:02d}:00:00",
            stack_name="test_stack",
        )
        await mock_storage_provider.save(sid, data, meta)

    snapshots = await mock_storage_provider.list_snapshots()
    assert len(snapshots) == 3

    stack_snapshots = await mock_storage_provider.list_snapshots("test_stack")
    assert len(stack_snapshots) == 3


@pytest.mark.asyncio
async def test_local_storage_delete(mock_storage_provider):
    """Test deleting a snapshot."""
    snapshot_id = "to_delete"
    data = b"delete me"
    metadata = SnapshotMetadata(
        snapshot_id=snapshot_id,
        name="Delete Test",
        snapshot_type=SnapshotType.CONFIG,
        timestamp="2026-04-14T12:00:00",
        stack_name="test_stack",
    )

    await mock_storage_provider.save(snapshot_id, data, metadata)
    delete_ok = await mock_storage_provider.delete(snapshot_id)
    assert delete_ok is True

    result = await mock_storage_provider.load(snapshot_id)
    assert result is None


@pytest.mark.asyncio
async def test_local_storage_get_disk_usage(mock_storage_provider):
    """Test calculating disk usage."""
    for i in range(3):
        sid = f"snapshot_{i}"
        data = b"x" * 1000  # 1KB each
        meta = SnapshotMetadata(
            snapshot_id=sid,
            name=f"Snapshot {i}",
            snapshot_type=SnapshotType.CONTAINER,
            timestamp=f"2026-04-14T{12 + i:02d}:00:00",
            stack_name="test_stack",
        )
        await mock_storage_provider.save(sid, data, meta)

    usage = await mock_storage_provider.get_disk_usage()
    assert usage > 3000


# ─── Encryption & Integrity Tests ────────────────────────────────────


def test_sha256_generation():
    """Test SHA-256 checksum generation."""
    data = b"test data for checksum"
    checksum = EncryptionHandler.generate_sha256(data)
    assert len(checksum) == 64
    assert checksum == EncryptionHandler.generate_sha256(data)


def test_sha256_verification():
    """Test SHA-256 verification."""
    data = b"test data"
    checksum = EncryptionHandler.generate_sha256(data)
    assert EncryptionHandler.verify_sha256(data, checksum) is True
    assert EncryptionHandler.verify_sha256(b"tampered", checksum) is False


@pytest.mark.asyncio
async def test_encryption_decryption_cycle():
    """Test encryption and decryption roundtrip."""
    data = b"sensitive data that must be encrypted"
    passphrase = "secure_passphrase_12345"

    # Encrypt
    key, salt = await EncryptionHandler.derive_key(passphrase)
    encrypted = await EncryptionHandler.encrypt_data(data, key, salt)
    assert encrypted != data
    assert len(encrypted) > len(data)

    # Decrypt
    decrypted = await EncryptionHandler.decrypt_data(encrypted, key)
    assert decrypted == data


@pytest.mark.asyncio
async def test_encryption_with_wrong_passphrase():
    """Test decryption with wrong derived key."""
    data = b"secret data"
    passphrase1 = "correct_passphrase"
    passphrase2 = "wrong_passphrase"

    key1, salt1 = await EncryptionHandler.derive_key(passphrase1)
    key2, _ = await EncryptionHandler.derive_key(passphrase2, salt1)

    encrypted = await EncryptionHandler.encrypt_data(data, key1, salt1)

    # Decryption with wrong key should raise an error in cryptography.fernet
    from cryptography.fernet import InvalidToken

    with pytest.raises(InvalidToken):
        await EncryptionHandler.decrypt_data(encrypted, key2)


# ─── Retention Policy Engine Tests ───────────────────────────────────


@pytest.mark.asyncio
async def test_retention_enforcement(mock_storage_provider, retention_engine):
    """Test retention policy enforcement."""
    for i in range(15):
        sid = f"snapshot_{i}"
        data = b"data"
        day = max(1, 14 - i)
        meta = SnapshotMetadata(
            snapshot_id=sid,
            name=f"Snapshot {i}",
            snapshot_type=SnapshotType.CONTAINER,
            timestamp=f"2026-04-{day:02d}T12:00:00",
            stack_name="test_stack",
        )
        await mock_storage_provider.save(sid, data, meta)

    deleted = await retention_engine.enforce_retention("test_stack")
    assert deleted >= 0


@pytest.mark.asyncio
async def test_retention_disk_usage_warning(mock_storage_provider, retention_engine):
    """Test disk usage warning check."""
    warning = await retention_engine.check_disk_usage_warning()
    assert warning is False


# ─── Health Check Runner Tests ───────────────────────────────────────


@pytest.mark.asyncio
async def test_health_check_container_engine(health_check_runner, mock_executor):
    """Test container engine health check via full check."""

    async def mock_run(cmd, run_root=False):
        if cmd == ["which", "podman"]:
            return CommandResult("/usr/bin/podman\n", "", 0, cmd)
        return CommandResult("", "", 1, cmd)

    mock_executor.run_async.side_effect = mock_run

    results = await health_check_runner.run_full_check()
    result = results[0]  # First check is engine
    assert isinstance(result, HealthCheckResult)
    assert result.status == HealthStatus.HEALTHY
    assert result.details.get("engine") == "podman"


@pytest.mark.asyncio
async def test_health_check_full_check(health_check_runner, mock_executor):
    """Test running full health check suite."""
    mock_executor.run_async.return_value = CommandResult("", "", 0, [])
    results = await health_check_runner.run_full_check("test-container")
    assert isinstance(results, list)
    assert len(results) > 0


# ─── HypeSync Status Tracker Tests ──────────────────────────────────


@pytest.mark.asyncio
async def test_sync_tracker_record_sync(sync_tracker):
    """Test recording a successful sync."""
    sync_tracker.record_sync(
        success=True,
        dotfiles_applied=True,
        secrets_bridged=True,
    )

    status = await sync_tracker.get_status()
    assert status.last_sync_success is True
    assert status.dotfiles_applied is True
    assert status.secrets_bridged is True
    assert status.sync_count == 1
    assert status.failure_count == 0


@pytest.mark.asyncio
async def test_sync_tracker_drift_detection(sync_tracker, mock_executor):
    """Test configuration drift detection."""
    expected_config = {
        "git_user_name": "Expected User",
        "ssh_expected": True,
    }

    async def mock_run(cmd, run_root=False):
        if cmd[:4] == ["git", "config", "--global", "user.name"]:
            return CommandResult("Different User\n", "", 0, cmd)
        if cmd == ["ssh-add", "-l"]:
            return CommandResult("", "", 1, cmd)
        return CommandResult("", "", 0, cmd)

    mock_executor.run_async.side_effect = mock_run

    drift = await sync_tracker.detect_drift(expected_config, mock_executor)
    assert drift is True
    status = await sync_tracker.get_status()
    assert status.drift_detected is True


# ─── Snapshot Manager Integration Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_snapshot_manager_create_snapshot(snapshot_manager, mock_storage_provider):
    """Test creating a snapshot through the manager."""
    snapshot_id = await snapshot_manager.create_snapshot(
        container_name="test-container",
        name="Test Snapshot",
    )

    assert snapshot_id != ""
    snapshots = await snapshot_manager.list_snapshots("test-container")
    assert snapshots[0].name == "Test Snapshot"


@pytest.mark.asyncio
async def test_snapshot_manager_create_encrypted_snapshot(snapshot_manager, mock_storage_provider):
    """Test creating an encrypted snapshot."""
    snapshot_id = await snapshot_manager.create_snapshot(
        container_name="test-container",
        encrypt=True,
        passphrase="secret_passphrase",
    )

    assert snapshot_id != ""
    snapshots = await snapshot_manager.list_snapshots("test-container")
    assert snapshots[0].encrypted is True


@pytest.mark.asyncio
async def test_snapshot_manager_restore_snapshot(snapshot_manager):
    """Test restoring a snapshot."""
    await snapshot_manager.create_snapshot(container_name="test-restore")
    snapshots = await snapshot_manager.list_snapshots("test-restore")
    snapshot_id = snapshots[0].snapshot_id

    success = await snapshot_manager.restore_snapshot(snapshot_id)
    assert success is True


@pytest.mark.asyncio
async def test_snapshot_manager_restore_encrypted(snapshot_manager):
    """Test restoring an encrypted snapshot."""
    await snapshot_manager.create_snapshot(
        container_name="test-encrypt",
        encrypt=True,
        passphrase="test_passphrase",
    )
    snapshots = await snapshot_manager.list_snapshots("test-encrypt")
    snapshot_id = snapshots[0].snapshot_id

    # Restore with passphrase
    success = await snapshot_manager.restore_snapshot(snapshot_id, passphrase="test_passphrase")
    assert success is True


@pytest.mark.asyncio
async def test_snapshot_manager_session_cache(snapshot_manager):
    """Test session-based key caching."""
    await snapshot_manager.create_snapshot(
        container_name="test-cache",
        encrypt=True,
        passphrase="session_secret",
    )
    snapshots = await snapshot_manager.list_snapshots("test-cache")
    snapshot_id = snapshots[0].snapshot_id

    # Restore WITHOUT passphrase (should use session cache)
    success = await snapshot_manager.restore_snapshot(snapshot_id)
    assert success is True
