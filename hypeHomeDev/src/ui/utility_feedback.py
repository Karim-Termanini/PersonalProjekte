"""User-visible feedback for utility pages (hosts, env, desktop) via ToastManager."""

from __future__ import annotations

import logging

from core.state import AppState

log = logging.getLogger(__name__)


def emit_utility_toast(message: str, ntype: str = "error", timeout: int = 8) -> None:
    """Show a toast via the event bus (ToastManager presents on the GTK main thread)."""
    bus = AppState.get().event_bus
    if bus:
        bus.emit("ui.notification", message=message, type=ntype, timeout=timeout)
    else:
        log.warning("%s", message)
