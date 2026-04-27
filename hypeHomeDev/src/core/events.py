"""HypeDevHome — Thread-safe event bus with debug tracing.

Provides a publish/subscribe mechanism for decoupled inter-component
communication within the application.

Supported event names (convention):
    - ``app.*``  — lifecycle events (started, shutdown, window-ready)
    - ``nav.*``  — navigation events (page-changed, page-loaded)
    - ``config.*`` — configuration events (changed, reset, saved)
    - ``error.*`` — error notification events (show-toast, critical)
    - ``theme.*`` — theme events (changed)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

Callback = Callable[..., Any]


class EventBus:
    """Thread-safe event bus supporting subscribe / emit / unsubscribe.

    Parameters
    ----------
    debug : bool
        When ``True`` every emit is logged with timing information.
    """

    def __init__(self, debug: bool = False) -> None:
        self._subscribers: dict[str, list[Callback]] = defaultdict(list)
        self._lock = threading.RLock()
        self._debug = debug

    # ── Public API ──────────────────────────────────────

    def subscribe(self, event_name: str, callback: Callback) -> None:
        """Register *callback* to be called when *event_name* is emitted."""
        if not isinstance(event_name, str) or not event_name:
            raise ValueError("event_name must be a non-empty string")
        with self._lock:
            if callback not in self._subscribers[event_name]:
                self._subscribers[event_name].append(callback)
                log.debug(
                    "Subscribed %s to '%s' (%d listeners)",
                    callback.__qualname__,
                    event_name,
                    len(self._subscribers[event_name]),
                )

    def unsubscribe(self, event_name: str, callback: Callback) -> None:
        """Remove *callback* from *event_name* listeners."""
        with self._lock:
            try:
                self._subscribers[event_name].remove(callback)
                log.debug("Unsubscribed %s from '%s'", callback.__qualname__, event_name)
            except ValueError:
                log.warning(
                    "Attempted to unsubscribe %s from '%s' but it was not registered",
                    callback.__qualname__,
                    event_name,
                )

    def emit(self, event_name: str, **kwargs: Any) -> None:
        """Invoke all callbacks registered for *event_name*.

        Each callback receives *kwargs* as keyword arguments.  Exceptions
        raised by individual callbacks are logged but do **not** prevent
        remaining callbacks from executing.
        """
        with self._lock:
            listeners = list(self._subscribers.get(event_name, []))

        if self._debug:
            log.debug("Emitting '%s' to %d listener(s)", event_name, len(listeners))

        for cb in listeners:
            start = time.monotonic()
            try:
                cb(**kwargs)
            except Exception:
                log.exception(
                    "Error in event handler %s for '%s'",
                    cb.__qualname__,
                    event_name,
                )
            if self._debug:
                elapsed_ms = (time.monotonic() - start) * 1000
                log.debug(
                    "Handler %s for '%s' took %.1fms", cb.__qualname__, event_name, elapsed_ms
                )

    def clear(self, event_name: str | None = None) -> None:
        """Remove all listeners for *event_name*, or **all** events if ``None``."""
        with self._lock:
            if event_name is None:
                self._subscribers.clear()
                log.debug("All event subscriptions cleared")
            else:
                self._subscribers.pop(event_name, None)
                log.debug("Subscriptions cleared for '%s'", event_name)

    @property
    def listener_count(self) -> int:
        """Total number of registered listeners across all events."""
        with self._lock:
            return sum(len(v) for v in self._subscribers.values())

    def has_listeners(self, event_name: str) -> bool:
        """Return ``True`` if any callbacks are registered for *event_name*."""
        with self._lock:
            return bool(self._subscribers.get(event_name))
