"""HypeDevHome — Background GitHub data monitor.

Periodically fetches issues, PRs, and other updates and publishes
them via the global EventBus.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING

from core.github.auth import GitHubAuthManager
from core.github.cache import get_github_disk_cache
from core.github.client import GitHubAPIError, get_client
from core.state import AppState

if TYPE_CHECKING:
    from core.events import EventBus

log = logging.getLogger(__name__)


class GitHubMonitor:
    """Background monitor for GitHub data.

    Publishes periodic updates to the EventBus:
    - ``github.issues``: list[dict]
    - ``github.prs``: list[dict]
    - ``github.mentions``: list[dict] (future)
    - ``github.assigned``: list[dict] (future)
    """

    def __init__(self, event_bus: EventBus, interval: float = 30.0) -> None:
        self._event_bus = event_bus
        self._interval = interval
        self._auth_manager = GitHubAuthManager()
        self._cache_manager = get_github_disk_cache()

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="GitHubMonitor", daemon=True)
            self._thread.start()
            log.info("GitHubMonitor started (interval=%fs)", self._interval)

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        with self._lock:
            if not self._thread:
                return
            self._stop_event.set()
            self._thread = None
            log.info("GitHubMonitor stopping...")

    def _run(self) -> None:
        """Poll on an interval; GitHub API runs on the app asyncio loop (same as widgets).

        A separate event loop here caused aiohttp to bind ClientSession to the wrong loop,
        breaking dashboard widgets with: "Timeout context manager should be used inside a task".
        """
        while not self._stop_event.is_set():
            app_loop = AppState.get().async_loop
            if self._auth_manager.is_authenticated() and app_loop and app_loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(self._refresh_data(), app_loop)
                try:
                    fut.result(timeout=180)
                except Exception:
                    log.exception("Error during GitHub data refresh")
            elif not self._auth_manager.is_authenticated():
                log.debug("GitHubMonitor: Not authenticated, skipping refresh")

            self._stop_event.wait(self._interval)

    async def _refresh_data(self) -> None:
        """Fetch fresh data from GitHub and emit events."""
        token = self._auth_manager.get_token()
        if not token:
            return

        client = await get_client()

        try:
            # 1. Fetch Issues
            issues = await client.get_issues()
            self._cache_manager.set("github.issues", issues)
            self._event_bus.emit("github.issues", data=issues)

            # 2. Fetch Pull Requests
            prs = await client.get_pull_requests()
            self._cache_manager.set("github.prs", prs)
            self._event_bus.emit("github.prs", data=prs)

            # TODO: Fetch mentions and assignments (Task B.5 dependencies)

            log.debug("GitHubMonitor: Data refreshed and emitted")

        except GitHubAPIError as e:
            log.warning("GitHub API error during refresh: %s", e)
            # We could emit an error event here
            self._event_bus.emit("github.error", message=str(e), status_code=e.status_code)
        except Exception as e:
            log.error("Unexpected error in GitHubMonitor: %s", e)

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        self._interval = max(15.0, float(value))
        log.info("GitHubMonitor interval updated to %fs", self._interval)
