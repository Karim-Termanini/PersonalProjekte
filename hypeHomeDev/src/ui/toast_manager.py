"""HypeDevHome — Centralized toast notification manager."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import gi

gi.require_version("Adw", "1")
from gi.repository import Adw, GLib  # noqa: E402

from core.state import AppState  # noqa: E402

if TYPE_CHECKING:
    from ui.window import HypeDevHomeWindow

log = logging.getLogger(__name__)


class ToastManager:
    """Singleton manager for application-wide notifications.

    Listens to 'error.show-toast' and 'ui.notification' events on the EventBus.
    """

    _instance: ToastManager | None = None

    def __init__(self, window: HypeDevHomeWindow) -> None:
        """Initialize the toast manager.

        Args:
            window: The main application window for presenting toasts.
        """
        self._window = window
        self._state = AppState.get()

        # Subscribe to events
        if self._state.event_bus:
            self._state.event_bus.subscribe("error.show-toast", self._on_show_toast)
            self._state.event_bus.subscribe("ui.notification", self._on_show_toast)
            log.debug("ToastManager subscribed to notification events")

    @classmethod
    def get(cls, window: HypeDevHomeWindow | None = None) -> ToastManager:
        """Get or create the singleton ToastManager instance."""
        if cls._instance is None:
            if window is None:
                raise ValueError("Window must be provided for initial ToastManager creation")
            cls._instance = cls(window)
        return cls._instance

    def _on_show_toast(self, **kwargs: Any) -> None:
        """Handle incoming toast request events.

        Expected kwargs:
            message (str): The toast content.
            timeout (int): Duration in seconds (optional).
            type (str): 'error', 'success', or 'info' (optional).
        """
        message = kwargs.get("message", "Unknown notification")
        timeout = kwargs.get("timeout", 5)
        ntype = kwargs.get("type", "info")

        # Toasts MUST be manipulated on the main thread
        GLib.idle_add(lambda: self.show_toast(message, timeout, ntype))

    def show_toast(self, message: str, timeout: int = 5, ntype: str = "info") -> None:
        """Immediately show a toast notification.

        Args:
            message: Text to display.
            timeout: Visibility duration in seconds.
            ntype: Type of notification for styling ('error', 'success', 'info').
        """
        toast = Adw.Toast.new(message)
        toast.set_timeout(timeout)

        # Basic styling based on type (simulated via prefix in Libadwaita 1.0)
        # Note: Future Libadwaita versions support custom templates,
        # but for now we keep it clean.
        if ntype == "error":
            log.error("TOAST (Error): %s", message)
            # toast.add_css_class("error") # If custom CSS is defined
        elif ntype == "success":
            log.info("TOAST (Success): %s", message)

        self._window.add_toast(toast)
        log.debug("Toast presented: %s", message)
