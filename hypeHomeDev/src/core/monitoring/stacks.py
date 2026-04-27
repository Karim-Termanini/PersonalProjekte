"""HypeDevHome — Background monitor for containerized stacks.

Periodically collects status and resource usage (CPU/Mem) for Distrobox and Toolbx
environments and broadcasts them via the global EventBus.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.events import EventBus
    from core.setup.environments import EnvironmentManager

log = logging.getLogger(__name__)


class StackMonitor:
    """Thread-safe background monitor for isolated stacks.

    Publishes periodic updates to the EventBus:
    - ``sysmon.stacks.update``: list[dict[str, Any]] containing container metadata and stats.
    """

    def __init__(
        self, event_bus: EventBus, env_manager: EnvironmentManager, interval: float = 5.0
    ) -> None:
        """Initialize the monitor.

        Args:
            event_bus: The application event bus to publish to.
            env_manager: The environment manager to query stacks from.
            interval: Polling internal in seconds.
        """
        self._event_bus = event_bus
        self._env_manager = env_manager
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                log.warning("StackMonitor is already running")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="StackMonitor", daemon=True)
            self._thread.start()
            log.info("StackMonitor started (interval=%fs)", self._interval)

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        with self._lock:
            if not self._thread:
                return

            self._stop_event.set()
            self._thread = None
            log.info("StackMonitor stopping...")

    def _run(self) -> None:
        """Main loop running in the background thread."""
        import asyncio

        # We need an event loop for the async calls into EnvironmentManager
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while not self._stop_event.is_set():
            try:
                loop.run_until_complete(self._collect_and_emit())
            except Exception:
                log.exception("Error during stack data collection")

            self._stop_event.wait(self._interval)

        loop.close()

    async def _collect_and_emit(self) -> None:
        """Perform a single collection cycle and publish events."""
        # 1. List all environments
        envs = await self._env_manager.list_environments()

        results = []
        for env in envs:
            name = env["name"]

            # 2. Get stats only for running environments to save resources
            stats: dict[str, Any] = {
                "cpu_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_io_mb": 0.0,
                "block_io_mb": 0.0,
            }

            if "Up" in env["status"] or "running" in env["status"]:
                stats = await self._env_manager.get_container_stats(name)

            results.append({**env, **stats})

        # 3. Emit update
        self._event_bus.emit("sysmon.stacks.update", stacks=results)
        log.debug("StackMonitor: Emitted update for %d stacks", len(results))

    @property
    def is_running(self) -> bool:
        """Return True if the monitor thread is active."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        self._interval = max(1.0, value)
        log.debug("StackMonitor interval updated to %fs", self._interval)
