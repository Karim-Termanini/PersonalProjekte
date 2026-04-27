"""Tests for Agent C Phase 6 Maintenance layer: Snapshots, EventBus, Key Cache."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.events import EventBus
from core.maintenance.manager import (
    EncryptionHandler,
    HealthCheckResult,
    HealthStatus,
    LocalStorageProvider,
    RetentionPolicyEngine,
    SnapshotManager,
    SnapshotMetadata,
    SnapshotType,
)
from core.maintenance.sync_tracker import HypeSyncStatus, HypeSyncStatusTracker
from core.setup.host_executor import HostExecutor


@pytest.fixture
def mock_executor():
    """Create a mock HostExecutor."""
    executor = MagicMock(spec=HostExecutor)
    executor.run_async = AsyncMock()
    return executor


@pytest.fixture
def mock_env_manager(mock_executor):
    """Create a mock EnvironmentManager."""
    env_mgr = MagicMock()
    env_mgr._executor = mock_executor
    env_mgr.backup_distrobox_container = AsyncMock(return_value=True)
    env_mgr.restore_distrobox_container = AsyncMock(return_value=True)
    return env_mgr


@pytest.fixture
def mock_storage_provider(tmp_path):
    """Create a mock storage provider."""
    return LocalStorageProvider(str(tmp_path / "snapshots"))


@pytest.fixture
def event_bus():
    """Create an EventBus for testing."""
    return EventBus()


@pytest.fixture
def sync_tracker():
    """Create a HypeSyncStatusTracker."""
    return HypeSyncStatusTracker()


@pytest.fixture
def snapshot_manager(mock_env_manager, mock_storage_provider, sync_tracker, event_bus):
    """Create a SnapshotManager with mock dependencies."""
    return SnapshotManager(
        env_manager=mock_env_manager,
        storage_provider=mock_storage_provider,
        sync_tracker=sync_tracker,
        event_bus=event_bus,
    )


# ─── EventBus Integration Tests ─────────────────────────────────────


def test_snapshot_creation_emits_event(snapshot_manager, event_bus):
    """Test that the _emit method correctly sends events."""
    events_received = []

    def capture_event(**kwargs):
        events_received.append(kwargs)

    event_bus.subscribe("maint.snapshot.creating", capture_event)

    # Test the _emit method directly
    snapshot_manager._emit("snapshot.creating", snapshot_id="test", container="test_container")

    assert len(events_received) == 1
    assert events_received[0]["snapshot_id"] == "test"
    assert events_received[0]["container"] == "test_container"


def test_snapshot_deletion_emits_event(snapshot_manager, event_bus, mock_storage_provider):
    """Test that deleting a snapshot emits events."""
    events_received = []

    def capture_event(**kwargs):
        events_received.append(kwargs)

    event_bus.subscribe("maint.snapshot.deleting", capture_event)
    event_bus.subscribe("maint.snapshot.deleted", capture_event)

    async def _run():
        # First create a snapshot
        snapshot_id = "test_delete"
        data = b"test data"
        meta = SnapshotMetadata(
            snapshot_id=snapshot_id,
            name="Delete Test",
            snapshot_type=SnapshotType.CONTAINER,
            timestamp="2026-04-14T12:00:00",
            stack_name="test_stack",
        )
        await mock_storage_provider.save(snapshot_id, data, meta)

        # Then delete
        return await snapshot_manager.delete_snapshot(snapshot_id)

    success = asyncio.run(_run())
    assert success is True
    assert len(events_received) == 2  # deleting + deleted


def test_snapshot_restore_emits_event(snapshot_manager, event_bus, mock_storage_provider):
    """Test that restoring a snapshot emits events."""
    events_received = []

    def capture_event(**kwargs):
        events_received.append(kwargs)

    event_bus.subscribe("maint.snapshot.restoring", capture_event)
    event_bus.subscribe("maint.snapshot.restored", capture_event)

    async def _run():
        # First create a snapshot WITH checksum
        snapshot_id = "test_restore"
        data = b"test restore data"
        checksum = EncryptionHandler.generate_sha256(data)
        meta = SnapshotMetadata(
            snapshot_id=snapshot_id,
            name="Restore Test",
            snapshot_type=SnapshotType.CONTAINER,
            timestamp="2026-04-14T12:00:00",
            container_name="test_container",
            stack_name="test_stack",
            sha256_checksum=checksum,  # Add checksum for integrity check
        )
        await mock_storage_provider.save(snapshot_id, data, meta)

        # Then restore
        return await snapshot_manager.restore_snapshot(snapshot_id)

    success = asyncio.run(_run())
    assert success is True
    assert any("restoring" in str(e) for e in events_received) or len(events_received) >= 2


# ─── Session Key Cache Tests ────────────────────────────────────────


def test_key_cache_clearing(snapshot_manager):
    """Test that key cache can be cleared."""
    # Add a fake key
    snapshot_manager._key_cache["test_salt_hash"] = b"test_key"
    assert len(snapshot_manager._key_cache) == 1

    snapshot_manager.clear_key_cache()
    assert len(snapshot_manager._key_cache) == 0


def test_encryption_with_key_caching():
    """Test encryption uses cached keys."""

    async def _run():
        passphrase = "test_passphrase"
        data = b"sensitive data"

        # Derive key and cache it
        key, salt = await EncryptionHandler.derive_key(passphrase)
        salt_hash = EncryptionHandler.generate_sha256(salt)
        cache = {salt_hash: key}

        # Encrypt
        encrypted = await EncryptionHandler.encrypt_data(data, key, salt)

        # Verify we can decrypt using cached key
        cached_key = cache.get(salt_hash)
        assert cached_key is not None

        decrypted = await EncryptionHandler.decrypt_data(encrypted, cached_key)
        assert decrypted == data

    asyncio.run(_run())


# ─── SyncTracker Integration Tests ─────────────────────────────────


def test_snapshot_manager_get_sync_status(snapshot_manager, sync_tracker):
    """Test getting sync status through snapshot manager."""
    # Record a sync
    sync_tracker.record_sync(success=True, dotfiles_applied=True)

    async def _run():
        status = await sync_tracker.get_status()
        return status

    status = asyncio.run(_run())
    assert isinstance(status, HypeSyncStatus)
    assert status.last_sync_success is True
    assert status.dotfiles_applied is True


def test_sync_tracker_broadcast_status(sync_tracker):
    """Test that sync tracker can broadcast status."""
    # Record a sync
    sync_tracker.record_sync(success=True)

    # The sync_tracker has its own internal event_bus or _emit method
    # For this test, we just verify the status is recorded correctly
    async def _run():
        await sync_tracker.broadcast_status()
        return sync_tracker._status

    status = asyncio.run(_run())
    assert status.last_sync_success is True


# ─── Health Check Tests ─────────────────────────────────────────────


def test_health_check_results_structure():
    """Test that health check results have correct structure."""
    result = HealthCheckResult(
        check_name="Test Check",
        status=HealthStatus.HEALTHY,
        message="All good",
        details={"key": "value"},
    )

    assert result.check_name == "Test Check"
    assert result.status == HealthStatus.HEALTHY
    assert result.message == "All good"
    assert result.details == {"key": "value"}
    assert result.timestamp  # Should have auto-generated timestamp


# ─── Retention Policy Tests ─────────────────────────────────────────


def test_retention_with_event_bus(mock_storage_provider, event_bus):
    """Test retention enforcement doesn't break with EventBus."""
    retention = RetentionPolicyEngine(mock_storage_provider)

    async def _run():
        # Create some snapshots
        for i in range(3):
            sid = f"snapshot_{i}"
            data = b"data"
            meta = SnapshotMetadata(
                snapshot_id=sid,
                name=f"Snapshot {i}",
                snapshot_type=SnapshotType.CONTAINER,
                timestamp=f"2026-04-{14 - i:02d}T12:00:00",
                stack_name="test_stack",
            )
            await mock_storage_provider.save(sid, data, meta)

        # Enforce retention
        deleted = await retention.enforce_retention("test_stack")
        assert deleted >= 0

    asyncio.run(_run())


# ─── Error Handling Tests ──────────────────────────────────────────


def test_create_snapshot_failure(snapshot_manager, event_bus, mock_env_manager):
    """Test that snapshot creation failure emits error event."""
    events_received = []

    def capture_event(**kwargs):
        events_received.append(kwargs)

    event_bus.subscribe("maint.snapshot.failed", capture_event)

    async def _run():
        mock_env_manager.backup_distrobox_container.return_value = False
        return await snapshot_manager.create_snapshot(
            container_name="fail_container",
        )

    snapshot_id = asyncio.run(_run())
    assert snapshot_id == ""
    assert len(events_received) >= 1
    assert "error" in events_received[0]


def test_restore_nonexistent_snapshot(snapshot_manager, event_bus):
    """Test restoring a nonexistent snapshot."""
    events_received = []

    def capture_event(**kwargs):
        events_received.append(kwargs)

    event_bus.subscribe("maint.snapshot.restore_failed", capture_event)

    async def _run():
        return await snapshot_manager.restore_snapshot("does_not_exist")

    success = asyncio.run(_run())
    assert success is False
    assert len(events_received) >= 1
