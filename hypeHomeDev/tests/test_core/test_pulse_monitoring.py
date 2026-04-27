from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import psutil
import pytest

from core.maintenance.pulse_manager import PulseManager
from core.monitoring.containers import (
    ContainerMonitor,
)


@pytest.fixture
def mock_executor():
    executor = MagicMock()
    executor.run_async = AsyncMock()
    return executor


@pytest.mark.asyncio
async def test_container_monitor_aggregates_and_deduplicates(mock_executor):
    """ContainerMonitor combines Distrobox/Podman/Docker without duplicates."""
    monitor = ContainerMonitor(mock_executor)

    async def fake_run_async(cmd: list[str]):
        if cmd[:2] == ["distrobox", "list"]:
            return SimpleNamespace(
                success=True,
                stdout="NAME  ID  STATUS  IMAGE\ndevbox  0  running  ghcr.io/example/devbox\n",
            )
        if cmd[0] == "podman":
            return SimpleNamespace(
                success=True,
                stdout='[{"Id": "devbox", "State": "running", "Names": ["devbox"], "Image": "ghcr.io/example/devbox"}, {"Id": "cache", "State": "exited", "Names": ["cache"], "Image": "redis:7"}]',
            )
        if cmd[0] == "docker":
            return SimpleNamespace(
                success=True,
                stdout='{"ID": "web", "State": "running", "Names": "web", "Image": "nginx:latest"}',
            )
        return SimpleNamespace(success=False, stdout="")

    mock_executor.run_async.side_effect = fake_run_async

    with patch(
        "psutil.process_iter",
        return_value=[
            SimpleNamespace(info={"name": "dockerd", "cmdline": ["dockerd"], "pid": 123})
        ],
    ):
        await monitor._update_container_metrics()
        summary = monitor.get_container_summary()

    assert summary["total_containers"] == 3
    assert summary["running_containers"] == 2
    assert summary["stopped_containers"] == 1


@pytest.mark.asyncio
async def test_pulse_manager_summary_contains_unified_telemetry(mock_executor, monkeypatch):
    """Pulse summary returns unified telemetry stream fields."""
    manager = PulseManager(mock_executor)
    await manager._container_monitor.stop()

    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 25.0)
    # get_summary() uses total/available (not .percent) for RAM used and %
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            total=16 * 1024**3,
            available=int(16 * 1024**3 * 0.6),
        ),
    )
    monkeypatch.setattr(psutil, "disk_usage", lambda path: SimpleNamespace(percent=30.0))
    monkeypatch.setattr(
        psutil, "net_io_counters", lambda: SimpleNamespace(bytes_recv=1000, bytes_sent=2000)
    )
    monkeypatch.setattr(
        psutil, "disk_io_counters", lambda: SimpleNamespace(read_bytes=3000, write_bytes=4000)
    )

    with patch.object(
        manager._container_monitor,
        "get_container_summary",
        return_value={
            "total_containers": 1,
            "running_containers": 1,
            "stopped_containers": 0,
            "total_cpu_percent": 5.0,
            "total_memory_mb": 256.0,
            "containers_by_engine": {"docker": 1},
            "engines_available": {},
            "last_updated": "now",
        },
    ):
        summary = manager.get_summary()
        telemetry = summary["telemetry"]

        assert summary["status"] == "Healthy"
        assert "network" in telemetry
        assert telemetry["containers"]["running_containers"] == 1


@pytest.mark.asyncio
async def test_pulse_manager_penalizes_when_all_containers_down(mock_executor, monkeypatch):
    """Health score drops when all discovered containers are down."""
    manager = PulseManager(mock_executor)
    await manager._container_monitor.stop()

    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 5.0)
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=1000, available=800),
    )
    monkeypatch.setattr(psutil, "disk_usage", lambda path: SimpleNamespace(percent=15.0))

    with patch.object(
        manager._container_monitor,
        "get_container_summary",
        return_value={
            "total_containers": 2,
            "running_containers": 0,
            "stopped_containers": 2,
            "total_cpu_percent": 0.0,
            "total_memory_mb": 0.0,
            "containers_by_engine": {"docker": 2},
            "engines_available": {},
            "last_updated": "now",
        },
    ):
        summary = manager.get_summary()
        # Initial 100 - 10 (all down penalty) = 90
        assert summary["overall_score"] == 90
