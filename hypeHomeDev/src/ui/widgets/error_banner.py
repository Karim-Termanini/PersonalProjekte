"""HypeDevHome — Error banner widget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class ErrorBanner(Gtk.Box):
    """Dismissable inline error banner with optional retry action.

    Parameters
    ----------
    message : str
        Error text displayed to the user.
    retry : callable, optional
        Called when the "Retry" button is clicked.
    on_dismiss : callable, optional
        Called when the banner is closed.
    """

    def __init__(
        self,
        message: str,
        retry: Callable[[], None] | None = None,
        on_dismiss: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_start=12,
            margin_end=12,
            margin_top=6,
            margin_bottom=6,
            **kwargs,
        )
        self.add_css_class("error-banner")

        # Icon
        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_pixel_size(16)
        self.append(icon)

        # Message label
        self._label = Gtk.Label(
            label=message,
            hexpand=True,
            halign=Gtk.Align.START,
            wrap=True,
        )
        self.append(self._label)

        # Retry button
        if retry is not None:
            btn = Gtk.Button(label="Retry")
            btn.add_css_class("suggested-action")
            btn.connect("clicked", lambda *_btn: retry())
            self.append(btn)

        # Close button
        close_btn = Gtk.Button.new_from_icon_name("window-close-symbolic")
        close_btn.add_css_class("flat")
        close_btn.connect("clicked", lambda *_btn: self._close(on_dismiss))
        self.append(close_btn)

    # ── Properties ───────────────────────────────

    @property
    def message(self) -> str:
        return str(self._label.get_label())

    @message.setter
    def message(self, value: str) -> None:
        self._label.set_label(value)

    # ── Internal ─────────────────────────────────

    def _close(self, callback: Callable[[], None] | None) -> None:
        parent = self.get_parent()
        if isinstance(parent, Gtk.Widget) and hasattr(parent, "remove"):
            parent.remove(self)
        if callback:
            callback()
