"""HypeDevHome — Container Monitoring System.

Tracks Docker, Podman, and Distrobox containers with real-time health metrics.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

import psutil

from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


class ContainerEngine(Enum):
    """Supported container engines."""

    DOCKER = auto()
    PODMAN = auto()
    DISTROBOX = auto()
    UNKNOWN = auto()


class ContainerStatus(Enum):
    """Container status states."""

    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    CREATED = auto()
    EXITED = auto()
    UNKNOWN = auto()


@dataclass
class ContainerMetrics:
    """Real-time metrics for a container."""

    container_id: str
    name: str
    engine: ContainerEngine
    status: ContainerStatus
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    network_rx_mb: float = 0.0
    network_tx_mb: float = 0.0
    uptime_seconds: float = 0.0
    health_status: str = "unknown"
    image: str = ""
    command: str = ""
    ports: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    last_updated: str = ""

    def __post_init__(self) -> None:
        pass


class ContainerMonitor:
    """Monitors Docker, Podman, and Distrobox containers with unified metrics."""

    def __init__(self, executor: HostExecutor, polling_interval: float = 5.0) -> None:
        """Initialize the container monitor.

        Args:
            executor: Host executor for running container commands.
            polling_interval: How often to poll for container updates (seconds).
        """
        self._executor = executor
        self._polling_interval = polling_interval
        self._containers: dict[str, ContainerMetrics] = {}
        self._running = False
        self._task: asyncio.Task[Any] | None = None

        # Cache for engine availability
        self._engines_available: dict[ContainerEngine, bool] = {}

        log.info("ContainerMonitor initialized with %.1fs polling interval", polling_interval)

    async def start(self) -> None:
        """Start the container monitoring loop."""
        if self._running:
            log.warning("ContainerMonitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        log.info("ContainerMonitor started")

    async def stop(self) -> None:
        """Stop the container monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            import contextlib

            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        log.info("ContainerMonitor stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._update_container_metrics()
                await asyncio.sleep(self._polling_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Error in container monitoring loop: %s", e)
                await asyncio.sleep(self._polling_interval * 2)  # Back off on error

    async def _update_container_metrics(self) -> None:
        """Update metrics for all containers."""
        try:
            # Check which engines are available
            await self._detect_available_engines()

            # Collect containers from all available engines
            all_containers: list[ContainerMetrics] = []

            if self._engines_available.get(ContainerEngine.DOCKER, False):
                docker_containers = await self._get_docker_containers()
                all_containers.extend(docker_containers)

            if self._engines_available.get(ContainerEngine.PODMAN, False):
                podman_containers = await self._get_podman_containers()
                all_containers.extend(podman_containers)

            if self._engines_available.get(ContainerEngine.DISTROBOX, False):
                distrobox_containers = await self._get_distrobox_containers()
                all_containers.extend(distrobox_containers)

            # Update container cache
            new_cache: dict[str, ContainerMetrics] = {}
            for container in all_containers:
                container_id = container.container_id
                new_cache[container_id] = container

                # Update network stats if container was previously tracked
                if container_id in self._containers:
                    old = self._containers[container_id]
                    # Calculate network deltas if container is running
                    if (
                        container.status == ContainerStatus.RUNNING
                        and old.status == ContainerStatus.RUNNING
                    ):
                        # Network stats will be updated by psutil in _get_container_process_metrics
                        pass

            self._containers = new_cache

            # Update process metrics for running containers
            await self._update_process_metrics()

        except Exception as e:
            log.error("Failed to update container metrics: %s", e)

    async def _detect_available_engines(self) -> None:
        """Detect which container engines are available on the system."""
        engines_to_check = [
            (ContainerEngine.DOCKER, ["docker", "--version"]),
            (ContainerEngine.PODMAN, ["podman", "--version"]),
            (ContainerEngine.DISTROBOX, ["distrobox", "--version"]),
        ]

        for engine, cmd in engines_to_check:
            if engine not in self._engines_available:
                result = await self._executor.run_async(cmd)
                self._engines_available[engine] = result.success

                if result.success:
                    log.debug("Detected %s engine", engine.name)
                else:
                    log.debug("%s engine not available", engine.name)

    async def _get_docker_containers(self) -> list[ContainerMetrics]:
        """Get Docker containers using docker CLI."""
        containers: list[ContainerMetrics] = []

        # Get container list in JSON format
        result = await self._executor.run_async(["docker", "ps", "-a", "--format", "{{json .}}"])

        if not result.success:
            return containers

        # Parse each line as JSON
        for line in result.stdout.strip().splitlines():
            if not line:
                continue

            try:
                data = json.loads(line)

                # Map Docker status to our status enum
                status_str = data.get("State", "").lower()
                status = self._map_docker_status(status_str)

                container = ContainerMetrics(
                    container_id=data.get("ID", "")[:12],
                    name=data.get("Names", ""),
                    engine=ContainerEngine.DOCKER,
                    status=status,
                    image=data.get("Image", ""),
                    command=data.get("Command", ""),
                    created_at=data.get("CreatedAt", ""),
                    last_updated=datetime.now().isoformat(),
                )

                # Parse ports
                ports_str = data.get("Ports", "")
                if ports_str:
                    container.ports = [p.strip() for p in ports_str.split(",") if p.strip()]

                containers.append(container)

            except json.JSONDecodeError as e:
                log.warning("Failed to parse Docker container JSON: %s", e)
                continue

        return containers

    async def _get_podman_containers(self) -> list[ContainerMetrics]:
        """Get Podman containers using podman CLI."""
        containers: list[ContainerMetrics] = []

        # Get container list in JSON format
        result = await self._executor.run_async(["podman", "ps", "-a", "--format", "json"])

        if not result.success:
            return containers

        try:
            data = json.loads(result.stdout)
            if not isinstance(data, list):
                return containers

            for item in data:
                # Map Podman status to our status enum
                status_str = item.get("State", "").lower()
                status = self._map_podman_status(status_str)

                container = ContainerMetrics(
                    container_id=item.get("Id", "")[:12],
                    name=item.get("Names", [""])[0],
                    engine=ContainerEngine.PODMAN,
                    status=status,
                    image=item.get("Image", ""),
                    command=item.get("Command", ""),
                    created_at=item.get("Created", ""),
                    last_updated=datetime.now().isoformat(),
                )

                # Parse ports
                ports = item.get("Ports", [])
                if ports:
                    container.ports = [str(p) for p in ports]

                # Parse labels
                labels = item.get("Labels", {})
                if labels:
                    container.labels = labels

                containers.append(container)

        except json.JSONDecodeError as e:
            log.warning("Failed to parse Podman container JSON: %s", e)

        return containers

    async def _get_distrobox_containers(self) -> list[ContainerMetrics]:
        """Get Distrobox containers using distrobox CLI."""
        containers: list[ContainerMetrics] = []

        # Get container list
        result = await self._executor.run_async(["distrobox", "list", "--no-color"])

        if not result.success:
            return containers

        # Parse distrobox list output
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:  # Header + data
            return containers

        # Skip header line
        for line in lines[1:]:
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) >= 4:
                name = parts[0]
                container_id = parts[1]
                status_str = parts[2].lower()
                image = parts[3]

                # Map Distrobox status
                status = self._map_distrobox_status(status_str)

                container = ContainerMetrics(
                    container_id=container_id[:12] if container_id else name,
                    name=name,
                    engine=ContainerEngine.DISTROBOX,
                    status=status,
                    image=image,
                    last_updated=datetime.now().isoformat(),
                )

                containers.append(container)

        return containers

    async def _update_process_metrics(self) -> None:
        """Update CPU and memory metrics for running containers using psutil."""
        try:
            # Get all running container processes
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = proc.info["cmdline"]
                    if not cmdline:
                        continue

                    # Check if this is a container runtime process
                    cmd_str = " ".join(cmdline)
                    container_id = None

                    # Look for container IDs in command line
                    if "docker" in cmd_str or "containerd" in cmd_str:
                        # Extract container ID from command line
                        for part in cmdline:
                            if len(part) == 64 or (len(part) == 12 and part.isalnum()):
                                container_id = part[:12]
                                break

                    if container_id and container_id in self._containers:
                        container = self._containers[container_id]
                        if container.status == ContainerStatus.RUNNING:
                            # Get CPU and memory usage
                            try:
                                cpu_percent = proc.cpu_percent(interval=0.1)
                                memory_info = proc.memory_info()

                                container.cpu_percent = cpu_percent
                                container.memory_mb = (
                                    memory_info.rss / 1024 / 1024
                                )  # Convert to MB
                                container.memory_percent = proc.memory_percent()
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

        except Exception as e:
            log.error("Error updating process metrics: %s", e)

    def _map_docker_status(self, status: str) -> ContainerStatus:
        """Map Docker status string to ContainerStatus enum."""
        status_lower = status.lower()
        if "running" in status_lower:
            return ContainerStatus.RUNNING
        elif "paused" in status_lower:
            return ContainerStatus.PAUSED
        elif "exited" in status_lower or "stopped" in status_lower:
            return ContainerStatus.STOPPED
        elif "created" in status_lower:
            return ContainerStatus.CREATED
        else:
            return ContainerStatus.UNKNOWN

    def _map_podman_status(self, status: str) -> ContainerStatus:
        """Map Podman status string to ContainerStatus enum."""
        status_lower = status.lower()
        if status_lower == "running":
            return ContainerStatus.RUNNING
        elif status_lower == "paused":
            return ContainerStatus.PAUSED
        elif status_lower in ["exited", "stopped"]:
            return ContainerStatus.STOPPED
        elif status_lower == "created":
            return ContainerStatus.CREATED
        else:
            return ContainerStatus.UNKNOWN

    def _map_distrobox_status(self, status: str) -> ContainerStatus:
        """Map Distrobox status string to ContainerStatus enum."""
        status_lower = status.lower()
        if status_lower == "running":
            return ContainerStatus.RUNNING
        elif status_lower in ["exited", "stopped"]:
            return ContainerStatus.STOPPED
        else:
            return ContainerStatus.UNKNOWN

    def get_container_metrics(self) -> list[ContainerMetrics]:
        """Get current container metrics.

        Returns:
            List of ContainerMetrics objects for all detected containers.
        """
        return list(self._containers.values())

    def get_container_summary(self) -> dict[str, Any]:
        """Get summary statistics for all containers.

        Returns:
            Dictionary with container summary statistics.
        """
        total = len(self._containers)
        running = sum(1 for c in self._containers.values() if c.status == ContainerStatus.RUNNING)
        stopped = sum(1 for c in self._containers.values() if c.status == ContainerStatus.STOPPED)

        # Calculate resource usage
        total_cpu = sum(c.cpu_percent for c in self._containers.values())
        total_memory_mb = sum(c.memory_mb for c in self._containers.values())

        # Count by engine
        by_engine = {
            "docker": sum(
                1 for c in self._containers.values() if c.engine == ContainerEngine.DOCKER
            ),
            "podman": sum(
                1 for c in self._containers.values() if c.engine == ContainerEngine.PODMAN
            ),
            "distrobox": sum(
                1 for c in self._containers.values() if c.engine == ContainerEngine.DISTROBOX
            ),
        }

        return {
            "total_containers": total,
            "running_containers": running,
            "stopped_containers": stopped,
            "total_cpu_percent": total_cpu,
            "total_memory_mb": total_memory_mb,
            "containers_by_engine": by_engine,
            "engines_available": self._engines_available,
            "last_updated": datetime.now().isoformat(),
        }

    async def get_container_details(self, container_id: str) -> ContainerMetrics | None:
        """Get detailed metrics for a specific container.

        Args:
            container_id: Short or full container ID.

        Returns:
            ContainerMetrics object or None if not found.
        """
        # Try to find by full ID or short ID
        for cid, container in self._containers.items():
            if cid.startswith(container_id) or container.container_id.startswith(container_id):
                return container

        return None

    def is_running(self) -> bool:
        """Check if the monitor is running."""
        return self._running
