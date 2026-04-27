import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.events import EventBus
from core.maintenance.logger import ActivityLogger
from core.maintenance.manager import SnapshotManager
from core.setup.environments import EnvironmentManager


@pytest.mark.asyncio
async def test_integration(tmp_path: Path) -> None:
    print("Testing ActivityLogger and Snapshot Auditor integration...")

    log_file = tmp_path / "test_activity.json"

    # Setup
    event_bus = EventBus(debug=True)
    activity_logger = ActivityLogger(log_path=str(log_file))

    def on_maint_event(event_name, **kwargs):
        activity_logger.log_event(event_name, **kwargs)

    for evt in ["maint.snapshot.creating", "maint.audit.started", "maint.audit.complete"]:
        event_bus.subscribe(evt, lambda _evt=evt, **k: on_maint_event(_evt, **k))

    env_manager = MagicMock(spec=EnvironmentManager)
    env_manager._executor = MagicMock()
    manager = SnapshotManager(env_manager, event_bus=event_bus)

    # 1. Trigger Audit
    print("Triggering audit...")
    await manager.audit_all_snapshots()

    # 2. Check log
    with open(log_file) as f:
        logs = json.load(f)
        print(f"Logged items: {len(logs)}")
        for entry in logs:
            print(f"- {entry['event']} ({entry['status']})")

    assert len(logs) >= 2
    print("Integration test passed!")

    # Cleanup (tmp_path is discarded by pytest)
    if log_file.exists():
        log_file.unlink()


if __name__ == "__main__":
    import tempfile

    async def _cli() -> None:
        with tempfile.TemporaryDirectory() as d:
            await test_integration(Path(d))

    asyncio.run(_cli())
