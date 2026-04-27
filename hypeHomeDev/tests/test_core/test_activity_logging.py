"""Tests for Phase 7 activity logging and snapshot auditing."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from core.events import EventBus
from core.maintenance.logger import ActivityLogger
from core.maintenance.manager import SnapshotManager
from core.maintenance.storage import LocalStorageProvider, SnapshotMetadata, SnapshotType


def test_maintenance_event_persists_to_activity_log(tmp_path: Path) -> None:
    """Emitting maint events writes records into activity.json."""
    log_path = tmp_path / "activity.json"
    logger = ActivityLogger(log_path=log_path)
    event_bus = EventBus()

    def log_event(event_name: str, payload: dict) -> None:
        status = "failed" if "failed" in event_name or "error" in payload else "success"
        logger.log_event(event_name, status=status, **payload)

    event_bus.subscribe(
        "maint.snapshot.created",
        lambda **kwargs: log_event("maint.snapshot.created", kwargs),
    )

    event_bus.emit("maint.snapshot.created", snapshot_id="snap_1", encrypted=True)

    content = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(content) == 1
    assert content[0]["event"] == "maint.snapshot.created"
    assert content[0]["details"]["snapshot_id"] == "snap_1"


def test_audit_all_snapshots_detects_tampering(tmp_path: Path) -> None:
    """Audit should fail snapshot when stored data is tampered."""
    storage = LocalStorageProvider(base_dir=tmp_path / "snapshots")
    event_bus = EventBus()
    env_manager = SimpleNamespace(_executor=SimpleNamespace())
    manager = SnapshotManager(
        env_manager=env_manager, storage_provider=storage, event_bus=event_bus
    )

    snapshot_id = "tampered_case"
    original_data = b"original data"
    metadata = SnapshotMetadata(
        snapshot_id=snapshot_id,
        name="tampered",
        snapshot_type=SnapshotType.CONFIG,
        timestamp="2026-04-14T00:00:00",
        stack_name="system",
        sha256_checksum=hashlib.sha256(original_data).hexdigest(),
        size_bytes=len(original_data),
    )

    asyncio.run(storage.save(snapshot_id, original_data, metadata))

    tampered_path = tmp_path / "snapshots" / "system" / f"{snapshot_id}.tar.gz"
    tampered_path.write_bytes(b"tampered data")

    result = asyncio.run(manager.audit_all_snapshots())
    assert result["total"] == 1
    assert result["failed"] == 1
    assert snapshot_id in result["tampered_ids"]
