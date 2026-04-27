"""HypeDevHome — Error handling and user notification system.

Provides toast notifications, error dialogs, and centralized error
reporting via the event bus.

Usage
-----
Show a quick toast message::

    show_toast("Settings saved", level=ToastLevel.SUCCESS)

Show an error toast with a retry button::

    show_toast("Connection failed", level=ToastLevel.ERROR, retry=on_retry)

Show a blocking error dialog for critical failures::

    show_error_dialog("Failed to load config", details="...")
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from enum import Enum
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

log = logging.getLogger(__name__)


class ToastLevel(Enum):
    """Severity levels for toast notifications."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


# ── Toast notifications ─────────────────────────────────


def show_toast(
    message: str,
    level: ToastLevel = ToastLevel.INFO,
    timeout: int = 3,
    button_label: str | None = None,
    button_action: Callable[[], None] | None = None,
    parent: Adw.ToastOverlay | None = None,
) -> None:
    """Display a toast notification on the given toast overlay.

    Parameters
    ----------
    message : str
        Text to display.
    level : ToastLevel
        Severity — currently only affects button styling when provided.
    timeout : int
        Seconds before the toast disappears (default 3).
    button_label : str | None
        Optional label for an action button.
    button_action : Callable[[], None] | None
        Callback invoked when the action button is clicked.
    parent : Adw.ToastOverlay | None
        The toast overlay to attach to.  If ``None`` the active window's
        toast overlay is looked up automatically.
    """
    if parent is None:
        parent = _get_active_toast_overlay()
        if parent is None:
            log.error("No toast overlay available — toast not shown: %s", message)
            return

    toast = Adw.Toast.new(message)
    toast.set_timeout(timeout)

    if button_label and button_action:
        toast.set_button_label(button_label)

        def _on_clicked(_toast: Adw.Toast) -> None:
            try:
                button_action()
            except Exception:
                log.exception("Error in toast button action for '%s'", message)

        toast.connect("dismissed", _on_clicked)

    parent.add_toast(toast)
    log.debug("Toast shown [%s]: %s", level.value, message)


def show_error_toast(
    message: str,
    retry: Callable[[], None] | None = None,
    parent: Adw.ToastOverlay | None = None,
) -> None:
    """Convenience: show an error toast with an optional retry button."""
    show_toast(
        message,
        level=ToastLevel.ERROR,
        button_label="Retry" if retry else None,
        button_action=retry,
        parent=parent,
    )


# ── Error dialog ────────────────────────────────────────


def show_error_dialog(
    title: str,
    message: str,
    details: str | None = None,
    parent: Gtk.Window | None = None,
) -> None:
    """Show a blocking error dialog.

    Parameters
    ----------
    title : str
        Dialog title.
    message : str
        Short description of the error.
    details : str | None
        Additional context (e.g. traceback snippet).
    parent : Gtk.Window | None
        Parent window for modal presentation.
    """
    if parent is None:
        parent = _get_active_window()

    dialog = Adw.AlertDialog.new(title, message)
    dialog.add_response("ok", "_OK")
    dialog.set_default_response("ok")
    dialog.set_close_response("ok")

    if details:
        log.error("Error dialog details: %s", details)

    dialog.present(parent)
    log.warning("Error dialog shown: %s — %s", title, message)


# ── Internal helpers ────────────────────────────────────


def _get_active_toast_overlay() -> Adw.ToastOverlay | None:
    """Walk the active window's children looking for an Adw.ToastOverlay."""
    active = _get_active_window()
    if active is None:
        return None
    # Walk children to find a ToastOverlay
    return _find_widget_by_type(active, Adw.ToastOverlay)


def _get_active_window() -> Gtk.Window | None:
    """Return the currently active Gtk.Window."""
    app = Gio.Application.get_default()
    if app is None or not isinstance(app, Gtk.Application):
        return None
    window = app.get_active_window()
    if window is None:
        return None
    return window


def _find_widget_by_type(widget: Gtk.Widget, widget_type: type[Any]) -> Any | None:
    """Recursively search a widget's children for a given type."""
    if isinstance(widget, widget_type):
        return widget
    # Try common container patterns
    if hasattr(widget, "get_child"):
        child = widget.get_child()
        if child:
            return _find_widget_by_type(child, widget_type)
    if hasattr(widget, "get_content"):
        content = widget.get_content()
        if content:
            return _find_widget_by_type(content, widget_type)
    return None
