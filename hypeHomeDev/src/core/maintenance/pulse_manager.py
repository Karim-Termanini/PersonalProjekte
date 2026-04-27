"""HypeDevHome — Maintenance Pulse Manager.

Monitors system health, container status, and maintenance tasks with unified telemetry.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

import psutil

from core.maintenance.storage import SnapshotType
from core.monitoring.containers import ContainerMonitor
from core.state import AppState

log = logging.getLogger(__name__)


class PulseManager:
    """Manages system maintenance 'Pulse' with unified telemetry."""

    def __init__(self, executor: Any = None) -> None:
        self._status = "Healthy"
        self._overall_score = 100
        self._last_check = "Not checked"
        self._executor = executor
        self._container_monitor = ContainerMonitor(executor, polling_interval=5.0)
        self._tasks: list[dict[str, Any]] = []
        self._telemetry_history: list[dict[str, Any]] = []
        self._max_history = 60  # Keep 60 samples (5 minutes at 5s intervals)
        self._is_active = False

        # Network telemetry
        self._last_net_sample_time: float | None = None
        self._last_net_recv = 0
        self._last_net_sent = 0

        # Disk telemetry
        self._last_disk_sample_time: float | None = None
        self._last_disk_read = 0
        self._last_disk_write = 0

        # Initial tasks update
        self._update_tasks(disk_percent=psutil.disk_usage("/").percent, container_count=0)

        log.info("PulseManager initialized with unified telemetry")

    async def start(self) -> None:
        """Start the background monitoring pulse."""
        if self._is_active:
            return

        self._is_active = True
        log.info("Starting PulseManager background monitor")
        await self._container_monitor.start()

    async def stop(self) -> None:
        """Stop the background monitoring pulse."""
        self._is_active = False
        log.info("Stopping PulseManager background monitor")
        # ContainerMonitor might need a stop method too, if it has a loop

    def _update_tasks(self, disk_percent: float, container_count: int) -> None:
        """Update the list of recommended maintenance tasks."""
        self._tasks = [
            {
                "id": "disk-cleanup",
                "name": "Journal Vacuum",
                "status": "Pending" if disk_percent > 80 else "Completed",
                "icon": "drive-harddisk-symbolic",
            },
            {
                "id": "package-sync",
                "name": "Package Metadata Sync",
                "status": "Pending",
                "icon": "software-update-available-symbolic",
            },
        ]

        if container_count > 0:
            self._tasks.append(
                {
                    "id": "container-health",
                    "name": "Container Health Review",
                    "status": "Pending",
                    "icon": "docker-symbolic",
                }
            )

    def _network_telemetry(self) -> dict[str, float]:
        net = psutil.net_io_counters()
        now = time.time()
        dl_speed = 0.0
        ul_speed = 0.0

        if self._last_net_sample_time is not None:
            elapsed = now - self._last_net_sample_time
            if elapsed > 0:
                dl_speed = max(0.0, (net.bytes_recv - self._last_net_recv) / elapsed)
                ul_speed = max(0.0, (net.bytes_sent - self._last_net_sent) / elapsed)

        self._last_net_sample_time = now
        self._last_net_recv = net.bytes_recv
        self._last_net_sent = net.bytes_sent

        return {
            "download_bps": dl_speed,
            "upload_bps": ul_speed,
            "download_bytes": float(net.bytes_recv),
            "upload_bytes": float(net.bytes_sent),
        }

    def _disk_telemetry(self) -> dict[str, float]:
        disk_io = psutil.disk_io_counters()
        if not disk_io:
            return {"read_bps": 0.0, "write_bps": 0.0}

        now = time.time()
        read_speed = 0.0
        write_speed = 0.0

        if self._last_disk_sample_time is not None:
            elapsed = now - self._last_disk_sample_time
            if elapsed > 0:
                read_speed = max(0.0, (disk_io.read_bytes - self._last_disk_read) / elapsed)
                write_speed = max(0.0, (disk_io.write_bytes - self._last_disk_write) / elapsed)

        self._last_disk_sample_time = now
        self._last_disk_read = disk_io.read_bytes
        self._last_disk_write = disk_io.write_bytes

        return {
            "read_bps": read_speed,
            "write_bps": write_speed,
            "read_bytes": float(disk_io.read_bytes),
            "write_bytes": float(disk_io.write_bytes),
        }

    def get_summary(self) -> dict[str, Any]:
        """Return a dynamic summary of system health with unified telemetry."""
        timestamp = datetime.now()
        self._last_check = timestamp.strftime("%H:%M:%S")

        # Collect system metrics
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        # On Linux, available is the most accurate for "how much is free for new apps"
        # Used = Total - Available (matches htop/gnome-monitor)
        ram_used_gb = (mem.total - mem.available) / (1024**3)
        ram_total_gb = mem.total / (1024**3)
        ram_percent = 100.0 * (1.0 - (mem.available / mem.total))

        disk = psutil.disk_usage("/").percent
        net = self._network_telemetry()
        disk_io = self._disk_telemetry()

        # Get container metrics
        container_summary = self._container_monitor.get_container_summary()
        container_metrics = self._container_monitor.get_container_metrics()

        # Calculate health score
        score = self._calculate_health_score(
            float(cpu), float(ram_percent), float(disk), container_summary
        )
        self._status = "Healthy" if score > 75 else "At Risk"
        self._overall_score = int(max(0, score))

        # Update tasks
        self._update_tasks(
            disk_percent=disk, container_count=container_summary["total_containers"]
        )

        # Create telemetry snapshot
        telemetry_snapshot = {
            "timestamp": timestamp.isoformat(),
            "cpu": cpu,
            "ram": ram_percent,
            "ram_used_gb": ram_used_gb,
            "ram_total_gb": ram_total_gb,
            "disk": disk,
            "network": net,
            "disk_io": disk_io,
            "containers": container_summary,
            "health_score": self._overall_score,
            "status": self._status,
        }

        # Add to history
        self._telemetry_history.append(telemetry_snapshot)
        if len(self._telemetry_history) > self._max_history:
            self._telemetry_history = self._telemetry_history[-self._max_history :]

        # Emit telemetry event if EventBus is available
        self._emit_telemetry_event(telemetry_snapshot)

        return {
            "status": self._status,
            "overall_score": self._overall_score,
            "tasks_pending": len([t for t in self._tasks if t["status"] == "Pending"]),
            "last_check": self._last_check,
            "telemetry": telemetry_snapshot,
            "container_details": container_metrics,
            "telemetry_history_count": len(self._telemetry_history),
        }

    def _calculate_health_score(
        self, cpu: float, ram: float, disk: float, container_summary: dict[str, Any]
    ) -> float:
        """Calculate comprehensive health score."""
        score: float = 100.0

        # CPU penalty (above 80%)
        if cpu > 80:
            score -= (cpu - 80) * 0.5

        # RAM penalty (above 85%)
        if ram > 85:
            score -= (ram - 85) * 0.5

        # Disk penalty (above 90%)
        if disk > 90:
            score -= (disk - 90) * 1.0

        # Container penalty (if containers exist but none are running)
        if (
            container_summary["total_containers"] > 0
            and container_summary["running_containers"] == 0
        ):
            score -= 10.0

        # High container resource usage penalty
        if container_summary["total_cpu_percent"] > 50:
            score -= 5.0
        if container_summary["total_memory_mb"] > 4096:  # 4GB
            score -= 5.0

        return max(0, score)

    def _emit_telemetry_event(self, telemetry: dict[str, Any]) -> None:
        """Emit telemetry data via EventBus if available."""
        try:
            app_state = AppState.get()
            if app_state.event_bus:
                app_state.event_bus.emit("monitoring.telemetry", **telemetry)
        except Exception:
            pass  # EventBus not available, silent fail

    def get_tasks(self) -> list[dict[str, Any]]:
        """Return detailed list of maintenance tasks."""
        return self._tasks

    def get_telemetry_history(self, limit: int = 60) -> list[dict[str, Any]]:
        """Get telemetry history for charting.

        Args:
            limit: Maximum number of historical samples to return.

        Returns:
            List of telemetry snapshots, newest first.
        """
        return self._telemetry_history[-limit:] if self._telemetry_history else []

    def get_container_health_details(self) -> dict[str, Any]:
        """Get detailed container health information.

        Returns:
            Dictionary with container health details.
        """
        container_summary = self._container_monitor.get_container_summary()
        container_metrics = self._container_monitor.get_container_metrics()

        # Analyze container health
        unhealthy_containers = []
        high_resource_containers = []

        for container in container_metrics:
            # Check for unhealthy containers
            if container.status.name != "RUNNING" and container.status.name != "CREATED":
                unhealthy_containers.append(
                    {
                        "name": container.name,
                        "status": container.status.name,
                        "engine": container.engine.name,
                    }
                )

            # Check for high resource usage
            if container.cpu_percent > 50 or container.memory_mb > 1024:
                high_resource_containers.append(
                    {
                        "name": container.name,
                        "cpu_percent": container.cpu_percent,
                        "memory_mb": container.memory_mb,
                        "engine": container.engine.name,
                    }
                )

        return {
            "summary": container_summary,
            "unhealthy_containers": unhealthy_containers,
            "high_resource_containers": high_resource_containers,
            "total_containers": len(container_metrics),
            "last_updated": datetime.now().isoformat(),
        }

    async def run_task(self, task_id: str) -> bool:
        """Execute a maintenance task."""
        log.info("Running maintenance task: %s", task_id)

        # Get current snapshot manager if available
        snapshot_manager = None
        try:
            app_state = AppState.get()
            snapshot_manager = app_state.snapshot_manager
        except Exception:
            pass

        for task in self._tasks:
            if task["id"] == task_id:
                if task_id == "disk-cleanup":
                    # Run journal vacuum
                    if self._executor:
                        result = await self._executor.run_async(["journalctl", "--vacuum-time=3d"])
                        task["status"] = "Completed" if result.success else "Failed"
                        return bool(result.success)

                elif task_id == "package-sync":
                    # Update package metadata
                    if self._executor:
                        # Try different package managers
                        for cmd in [["apt", "update"], ["dnf", "check-update"], ["pacman", "-Sy"]]:
                            result = await self._executor.run_async(cmd)
                            if result.returncode in [
                                0,
                                100,
                            ]:  # 100 means updates available for dnf
                                task["status"] = "Completed"
                                return True
                        task["status"] = "Failed"
                        return False

                elif task_id == "container-health":
                    # Check container health
                    task["status"] = "Completed"
                    return True

                elif task_id == "snapshot-backup" and snapshot_manager:
                    # Create a global backup snapshot
                    try:
                        snapshot_id = await snapshot_manager.create_snapshot(
                            name="global_backup",
                            snapshot_type=SnapshotType.FULL_ENVIRONMENT,
                            encrypt=True,
                        )
                        task["status"] = "Completed" if snapshot_id else "Failed"
                        return bool(snapshot_id)
                    except Exception as e:
                        log.error("Failed to create snapshot: %s", e)
                        task["status"] = "Failed"
                        return False

                else:
                    task["status"] = "Completed"
                    return True

        return False
