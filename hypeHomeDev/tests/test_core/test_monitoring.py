"""Tests for Phase 7 Monitoring Expansion - Container tracking and unified telemetry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.maintenance.pulse_manager import PulseManager
from core.monitoring.containers import (
    ContainerEngine,
    ContainerMetrics,
    ContainerMonitor,
    ContainerStatus,
)


@pytest.fixture
def mock_executor():
    """Create a mock HostExecutor."""
    executor = MagicMock()
    executor.run_async = AsyncMock()
    return executor


@pytest.fixture
def container_monitor(mock_executor):
    """Create a ContainerMonitor with mock executor."""
    monitor = ContainerMonitor(mock_executor, polling_interval=0.1)
    # Don't start the monitoring loop for tests
    monitor._running = False
    return monitor


@pytest.fixture
async def pulse_manager(mock_executor):
    """Create a PulseManager with mock executor."""
    manager = PulseManager(mock_executor)
    # Stop the container monitor to avoid async task issues
    await manager._container_monitor.stop()
    return manager


@pytest.mark.asyncio
async def test_container_monitor_detects_engines(container_monitor, mock_executor):
    """Test that container monitor detects available engines."""
    # Mock engine detection
    mock_result = MagicMock()
    mock_result.success = True
    mock_executor.run_async.return_value = mock_result

    await container_monitor._detect_available_engines()

    # Should have checked for engines
    assert mock_executor.run_async.call_count >= 3


@pytest.mark.asyncio
async def test_container_monitor_get_container_summary(container_monitor):
    """Test container summary generation."""
    # Mock empty container list
    with patch.object(container_monitor, "_containers", {}):
        summary = container_monitor.get_container_summary()

        assert "total_containers" in summary
        assert "running_containers" in summary
        assert "stopped_containers" in summary
        assert "total_cpu_percent" in summary
        assert "total_memory_mb" in summary
        assert "containers_by_engine" in summary
        assert "engines_available" in summary
        assert "last_updated" in summary


@pytest.mark.asyncio
async def test_pulse_manager_telemetry_collection(pulse_manager):
    """Test that pulse manager collects unified telemetry."""
    # Mock system metrics
    with (
        patch("psutil.cpu_percent", return_value=25.0),
        patch("psutil.virtual_memory", return_value=MagicMock(percent=40.0)),
        patch("psutil.disk_usage", return_value=MagicMock(percent=30.0)),
        patch("psutil.net_io_counters", return_value=MagicMock(bytes_recv=1000, bytes_sent=2000)),
        patch(
            "psutil.disk_io_counters", return_value=MagicMock(read_bytes=3000, write_bytes=4000)
        ),
        patch.object(
            pulse_manager._container_monitor,
            "get_container_summary",
            return_value={
                "total_containers": 2,
                "running_containers": 1,
                "stopped_containers": 1,
                "total_cpu_percent": 15.5,
                "total_memory_mb": 512.0,
                "containers_by_engine": {"docker": 1, "podman": 1, "distrobox": 0},
                "engines_available": {},
                "last_updated": "2026-04-14T22:00:00",
            },
        ),
        patch.object(pulse_manager._container_monitor, "get_container_metrics", return_value=[]),
    ):
        summary = pulse_manager.get_summary()

        # Check structure
        assert "status" in summary
        assert "overall_score" in summary
        assert "tasks_pending" in summary
        assert "last_check" in summary
        assert "telemetry" in summary
        assert "container_details" in summary
        assert "telemetry_history_count" in summary

        # Check telemetry content
        telemetry = summary["telemetry"]
        assert "cpu" in telemetry
        assert "ram" in telemetry
        assert "disk" in telemetry
        assert "network" in telemetry
        assert "disk_io" in telemetry
        assert "containers" in telemetry
        assert "health_score" in telemetry
        assert "status" in telemetry

        # Check network telemetry
        assert "download_bps" in telemetry["network"]
        assert "upload_bps" in telemetry["network"]
        assert "download_bytes" in telemetry["network"]
        assert "upload_bytes" in telemetry["network"]

        # Check disk I/O telemetry
        assert "read_bps" in telemetry["disk_io"]
        assert "write_bps" in telemetry["disk_io"]
        assert "read_bytes" in telemetry["disk_io"]
        assert "write_bytes" in telemetry["disk_io"]


@pytest.mark.asyncio
async def test_pulse_manager_health_score_calculation():
    """Test health score calculation with various system states."""
    # Create a PulseManager without starting async tasks
    manager = PulseManager(None)
    manager._container_monitor._running = False

    test_cases = [
        # (cpu, ram, disk, container_summary, expected_min_score)
        (
            10.0,
            20.0,
            15.0,
            {
                "total_containers": 1,
                "running_containers": 1,
                "total_cpu_percent": 5.0,
                "total_memory_mb": 256.0,
            },
            95,
        ),
        (
            90.0,
            20.0,
            15.0,
            {
                "total_containers": 1,
                "running_containers": 1,
                "total_cpu_percent": 5.0,
                "total_memory_mb": 256.0,
            },
            85,
        ),  # High CPU penalty
        (
            10.0,
            90.0,
            15.0,
            {
                "total_containers": 1,
                "running_containers": 1,
                "total_cpu_percent": 5.0,
                "total_memory_mb": 256.0,
            },
            85,
        ),  # High RAM penalty
        (
            10.0,
            20.0,
            95.0,
            {
                "total_containers": 1,
                "running_containers": 1,
                "total_cpu_percent": 5.0,
                "total_memory_mb": 256.0,
            },
            90,
        ),  # High disk penalty
        (
            10.0,
            20.0,
            15.0,
            {
                "total_containers": 2,
                "running_containers": 0,
                "total_cpu_percent": 5.0,
                "total_memory_mb": 256.0,
            },
            90,
        ),  # No containers running
        (
            10.0,
            20.0,
            15.0,
            {
                "total_containers": 1,
                "running_containers": 1,
                "total_cpu_percent": 60.0,
                "total_memory_mb": 5120.0,
            },
            90,
        ),  # High container resources
    ]

    for cpu, ram, disk, container_summary, expected_min_score in test_cases:
        score = manager._calculate_health_score(cpu, ram, disk, container_summary)
        assert score >= expected_min_score
        assert 0 <= score <= 100


@pytest.mark.asyncio
async def test_pulse_manager_container_health_details():
    """Test container health details generation."""
    # Create a PulseManager without starting async tasks
    manager = PulseManager(None)
    manager._container_monitor._running = False

    # Mock container metrics
    mock_metrics = [
        ContainerMetrics(
            container_id="test1",
            name="container1",
            engine=ContainerEngine.DOCKER,
            status=ContainerStatus.RUNNING,
            cpu_percent=10.0,
            memory_mb=512.0,
            memory_percent=5.0,
        ),
        ContainerMetrics(
            container_id="test2",
            name="container2",
            engine=ContainerEngine.PODMAN,
            status=ContainerStatus.EXITED,
            cpu_percent=0.0,
            memory_mb=0.0,
            memory_percent=0.0,
        ),
        ContainerMetrics(
            container_id="test3",
            name="container3",
            engine=ContainerEngine.DISTROBOX,
            status=ContainerStatus.RUNNING,
            cpu_percent=60.0,  # High CPU
            memory_mb=2048.0,  # High memory (> 1GB)
            memory_percent=20.0,
        ),
    ]

    with (
        patch.object(
            manager._container_monitor,
            "get_container_summary",
            return_value={
                "total_containers": 3,
                "running_containers": 2,
                "stopped_containers": 1,
                "total_cpu_percent": 70.0,
                "total_memory_mb": 2560.0,
                "containers_by_engine": {"docker": 1, "podman": 1, "distrobox": 1},
                "engines_available": {},
                "last_updated": "2026-04-14T22:00:00",
            },
        ),
        patch.object(
            manager._container_monitor, "get_container_metrics", return_value=mock_metrics
        ),
    ):
        health_details = manager.get_container_health_details()

        assert "summary" in health_details
        assert "unhealthy_containers" in health_details
        assert "high_resource_containers" in health_details
        assert "total_containers" in health_details
        assert "last_updated" in health_details

        # Check unhealthy containers (EXITED is not RUNNING or CREATED)
        assert len(health_details["unhealthy_containers"]) == 1
        assert health_details["unhealthy_containers"][0]["name"] == "container2"

        # Check high resource containers
        assert len(health_details["high_resource_containers"]) == 1
        assert health_details["high_resource_containers"][0]["name"] == "container3"


@pytest.mark.asyncio
async def test_pulse_manager_telemetry_history():
    """Test telemetry history tracking."""
    # Create a PulseManager without starting async tasks
    manager = PulseManager(None)
    manager._container_monitor._running = False

    # Mock system metrics
    with (
        patch("psutil.cpu_percent", return_value=25.0),
        patch("psutil.virtual_memory", return_value=MagicMock(percent=40.0)),
        patch("psutil.disk_usage", return_value=MagicMock(percent=30.0)),
        patch("psutil.net_io_counters", return_value=MagicMock(bytes_recv=1000, bytes_sent=2000)),
        patch(
            "psutil.disk_io_counters", return_value=MagicMock(read_bytes=3000, write_bytes=4000)
        ),
        patch.object(
            manager._container_monitor,
            "get_container_summary",
            return_value={
                "total_containers": 0,
                "running_containers": 0,
                "stopped_containers": 0,
                "total_cpu_percent": 0.0,
                "total_memory_mb": 0.0,
                "containers_by_engine": {},
                "engines_available": {},
                "last_updated": "2026-04-14T22:00:00",
            },
        ),
        patch.object(manager._container_monitor, "get_container_metrics", return_value=[]),
    ):
        # Get multiple summaries to build history
        for _ in range(5):
            manager.get_summary()

        history = manager.get_telemetry_history()

        assert len(history) == 5
        assert all("timestamp" in entry for entry in history)
        assert all("cpu" in entry for entry in history)
        assert all("ram" in entry for entry in history)
        assert all("disk" in entry for entry in history)

        # Test limit parameter
        limited_history = manager.get_telemetry_history(limit=2)
        assert len(limited_history) == 2


def test_container_status_mapping():
    """Test container status mapping functions."""
    from core.monitoring.containers import ContainerMonitor

    monitor = ContainerMonitor(executor=None)

    # Test Docker status mapping
    assert monitor._map_docker_status("running") == ContainerStatus.RUNNING
    assert monitor._map_docker_status("paused") == ContainerStatus.PAUSED
    assert monitor._map_docker_status("exited") == ContainerStatus.STOPPED
    assert monitor._map_docker_status("stopped") == ContainerStatus.STOPPED
    assert monitor._map_docker_status("created") == ContainerStatus.CREATED
    assert monitor._map_docker_status("unknown") == ContainerStatus.UNKNOWN

    # Test Podman status mapping
    assert monitor._map_podman_status("running") == ContainerStatus.RUNNING
    assert monitor._map_podman_status("paused") == ContainerStatus.PAUSED
    assert monitor._map_podman_status("exited") == ContainerStatus.STOPPED
    assert monitor._map_podman_status("stopped") == ContainerStatus.STOPPED
    assert monitor._map_podman_status("created") == ContainerStatus.CREATED
    assert monitor._map_podman_status("unknown") == ContainerStatus.UNKNOWN

    # Test Distrobox status mapping
    assert monitor._map_distrobox_status("running") == ContainerStatus.RUNNING
    assert monitor._map_distrobox_status("exited") == ContainerStatus.STOPPED
    assert monitor._map_distrobox_status("stopped") == ContainerStatus.STOPPED
    assert monitor._map_distrobox_status("unknown") == ContainerStatus.UNKNOWN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
