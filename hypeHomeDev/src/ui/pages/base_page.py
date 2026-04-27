"""HypeDevHome - Base page class for all application pages.

Every top-level page in the sidebar inherits from ``BasePage``.  This
provides a consistent lifecycle (``on_shown`` / ``on_hidden``), a
standard layout with an optional loading overlay, and lazy-init support.
"""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

log = logging.getLogger(__name__)


class BasePage(Gtk.Box):
    """Abstract base for all navigable pages.

    Subclasses **must** override :meth:`build_content` which is called
    lazily on first display.  Optionally override :meth:`on_shown` and
    :meth:`on_hidden` for page-specific lifecycle work (e.g. starting /
    stopping timers).
    """

    page_title: str = "Page"
    page_icon: str = "document-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._built = False

        # ── Loading overlay (shown until build_content finishes) ──
        self._spinner = Gtk.Spinner()
        self._spinner.start()
        self._spinner.set_vexpand(True)
        self._spinner.set_hexpand(True)
        self._spinner.set_halign(Gtk.Align.CENTER)
        self._spinner.set_valign(Gtk.Align.CENTER)
        self.append(self._spinner)

    # ── Lifecycle ───────────────────────────────────────

    def ensure_built(self) -> None:
        """Build page content exactly once (lazy initialisation)."""
        if self._built:
            return
        self._built = True
        self.remove(self._spinner)
        self.build_content()
        log.debug("Page '%s' built", self.page_title)

    def on_shown(self) -> None:
        """Called each time the page becomes visible."""
        self.ensure_built()
        log.debug("Page '%s' shown", self.page_title)

    def on_hidden(self) -> None:
        """Called each time the page is navigated away from."""
        log.debug("Page '%s' hidden", self.page_title)

    # ── Subclass API ────────────────────────────────────

    def build_content(self) -> None:
        """Override to populate the page with widgets.

        Called exactly once, lazily, on first display.
        """
        raise NotImplementedError

    def get_window_title(self) -> str:
        """Title shown in the main window header (sidebar page or nested view)."""
        return self.page_title

    def show_sidebar_toggle_in_header(self) -> bool:
        """Whether the window header shows the sidebar show/hide button (start pack)."""
        return True

    def get_header_actions(self) -> list[Gtk.Widget]:
        """Return extra widgets to insert into the header bar.

        Override to add page-specific action buttons.
        """
        return []

    def handle_escape(self) -> bool:
        """Handle Escape (e.g. pop a sub-view). Return True if the key was handled."""
        return False
