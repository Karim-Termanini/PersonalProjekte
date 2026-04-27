"""HypeDevHome — Application-wide singleton state.

Holds references that many modules need (config, logger, event bus)
without introducing circular imports.  Access the instance via
``AppState.get()``.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from enum import Enum
from typing import TYPE_CHECKING, Any

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from config.manager import ConfigManager
    from core.events import EventBus
    from core.maintenance.logger import ActivityLogger
    from core.maintenance.manager import SnapshotManager
    from core.maintenance.pulse_manager import PulseManager
    from core.maintenance.sync_tracker import HypeSyncStatusTracker
    from core.monitoring.stacks import StackMonitor
    from core.monitoring.system import SystemMonitor
    from core.setup.env_vars import EnvVarEngine
    from core.setup.environments import EnvironmentManager
    from core.setup.hosts import HostFileManager


class AppLifecycle(Enum):
    """Application lifecycle states."""

    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    SHUTTING_DOWN = "shutting_down"


class AppState:
    """Thread-safe singleton holding application-wide state.

    Manages:
    - Configuration and event bus references
    - Current navigation page
    - User preferences cache
    - Application lifecycle state
    - Last error tracking
    """

    _instance: AppState | None = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        # Core references
        self._config: ConfigManager | None = None
        self._event_bus: EventBus | None = None
        self._system_monitor: SystemMonitor | None = None
        self._stack_monitor: StackMonitor | None = None
        self._env_manager: EnvironmentManager | None = None
        self._host_manager: HostFileManager | None = None
        self._env_var_engine: EnvVarEngine | None = None
        self._snapshot_manager: SnapshotManager | None = None
        self._pulse_manager: PulseManager | None = None
        self._sync_tracker: HypeSyncStatusTracker | None = None
        self._activity_logger: ActivityLogger | None = None
        self._async_loop: asyncio.AbstractEventLoop | None = None
        self._current_page: str = "welcome"

        # Lifecycle state
        self._lifecycle: AppLifecycle = AppLifecycle.INITIALIZING

        # Error tracking
        self._last_error: Exception | None = None
        self._error_count: int = 0

        # Dashboard state
        self._dashboard_layout: list[dict[str, Any]] = []

        # Preferences cache (key-value, refreshed from config on demand)
        self._preferences: dict[str, Any] = {}

    # ── Singleton access ────────────────────────────────

    @classmethod
    def get(cls) -> AppState:
        """Return the global ``AppState`` instance (created on first call)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
                    log.debug("AppState singleton created")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton — useful for testing."""
        with cls._lock:
            cls._instance = None

    # ── Core references ─────────────────────────────────

    @property
    def config(self) -> ConfigManager | None:
        return self._config

    @config.setter
    def config(self, value: ConfigManager) -> None:
        self._config = value

    @property
    def event_bus(self) -> EventBus | None:
        return self._event_bus

    @event_bus.setter
    def event_bus(self, value: EventBus) -> None:
        self._event_bus = value

    @property
    def system_monitor(self) -> SystemMonitor | None:
        """Return the active system monitor service."""
        return self._system_monitor

    @system_monitor.setter
    def system_monitor(self, value: SystemMonitor) -> None:
        """Set the active system monitor service."""
        self._system_monitor = value

    @property
    def stack_monitor(self) -> StackMonitor | None:
        """Return the active stack monitor service."""
        return self._stack_monitor

    @stack_monitor.setter
    def stack_monitor(self, value: StackMonitor) -> None:
        """Set the active stack monitor service."""
        self._stack_monitor = value

    @property
    def environment_manager(self) -> EnvironmentManager | None:
        """Return the global environment manager."""
        return self._env_manager

    @environment_manager.setter
    def environment_manager(self, value: EnvironmentManager) -> None:
        """Set the global environment manager."""
        self._env_manager = value

    @property
    def host_manager(self) -> HostFileManager | None:
        """Return the global host file manager."""
        return self._host_manager

    @host_manager.setter
    def host_manager(self, value: HostFileManager) -> None:
        """Set the global host file manager."""
        self._host_manager = value

    @property
    def env_var_engine(self) -> EnvVarEngine | None:
        """Return the global environment variable engine."""
        return self._env_var_engine

    @env_var_engine.setter
    def env_var_engine(self, value: EnvVarEngine) -> None:
        """Set the global environment variable engine."""
        self._env_var_engine = value

    @property
    def snapshot_manager(self) -> SnapshotManager | None:
        """Return the global snapshot manager."""
        return self._snapshot_manager

    @snapshot_manager.setter
    def snapshot_manager(self, value: SnapshotManager) -> None:
        """Set the global snapshot manager."""
        self._snapshot_manager = value

    @property
    def pulse_manager(self) -> PulseManager | None:
        """Return the global pulse (health) manager."""
        return self._pulse_manager

    @pulse_manager.setter
    def pulse_manager(self, value: PulseManager) -> None:
        """Set the global pulse (health) manager."""
        self._pulse_manager = value

    @property
    def sync_tracker(self) -> HypeSyncStatusTracker | None:
        """Return the global HypeSync status tracker."""
        return self._sync_tracker

    @sync_tracker.setter
    def sync_tracker(self, value: HypeSyncStatusTracker) -> None:
        """Set the global HypeSync status tracker."""
        self._sync_tracker = value

    @property
    def activity_logger(self) -> ActivityLogger | None:
        """Return the global activity logger."""
        return self._activity_logger

    @activity_logger.setter
    def activity_logger(self, value: ActivityLogger) -> None:
        """Set the global activity logger."""
        self._activity_logger = value

    @property
    def async_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the global background asyncio event loop."""
        return self._async_loop

    @async_loop.setter
    def async_loop(self, value: asyncio.AbstractEventLoop) -> None:
        """Set the global background asyncio event loop."""
        self._async_loop = value

    # ── Navigation state ────────────────────────────────

    @property
    def current_page(self) -> str:
        return self._current_page

    def navigate_to(self, page: str) -> None:
        """Switch the current page and emit ``nav.page-changed``."""
        if self._current_page == page:
            return
        old_page = self._current_page
        self._current_page = page
        log.debug("Navigation: %s -> %s", old_page, page)
        if self._event_bus:
            self._event_bus.emit("nav.page-changed", old=old_page, new=page)

    # ── Lifecycle state ─────────────────────────────────

    @property
    def lifecycle(self) -> AppLifecycle:
        return self._lifecycle

    def set_lifecycle(self, state: AppLifecycle) -> None:
        """Update the lifecycle state."""
        self._lifecycle = state
        log.debug("Lifecycle changed to: %s", state.value)

    # ── Error tracking ──────────────────────────────────

    @property
    def last_error(self) -> Exception | None:
        return self._last_error

    def record_error(self, error: Exception) -> None:
        """Record an error for later inspection."""
        self._last_error = error
        self._error_count += 1
        log.error("Error recorded (total: %d): %s", self._error_count, error)

    @property
    def error_count(self) -> int:
        return self._error_count

    def reset_errors(self) -> None:
        """Clear error tracking."""
        self._last_error = None
        self._error_count = 0

    # ── Preferences cache ───────────────────────────────

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Return a cached preference value."""
        return self._preferences.get(key, default)

    def set_preference(self, key: str, value: Any) -> None:
        """Cache a preference value."""
        self._preferences[key] = value

    def load_preferences_from_config(self) -> None:
        """Reload the preferences cache from the configuration manager."""
        if self._config is None:
            log.warning("No config manager available to reload preferences")
            return
        self._preferences = self._config.get("preferences", {})
        log.debug("Preferences reloaded from config (%d keys)", len(self._preferences))

    @property
    def dashboard_layout(self) -> list[dict[str, Any]]:
        """Return the current dashboard layout."""
        return self._dashboard_layout

    @dashboard_layout.setter
    def dashboard_layout(self, value: list[dict[str, Any]]) -> None:
        """Update the dashboard layout."""
        self._dashboard_layout = value
        log.debug("Dashboard layout updated (%d widgets)", len(value))
