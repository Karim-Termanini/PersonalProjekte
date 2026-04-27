"""HypeDevHome — Accessibility utilities.

Provides helpers to ensure all interactive elements are accessible via
screen readers, keyboard navigation, and high-contrast themes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

# ── RTL locale helpers ─────────────────────────────────

_RTL_LOCALES = {"ar", "he", "fa", "ur"}


def is_rtl(locale: str) -> bool:
    """Return ``True`` if *locale* uses a right-to-left writing system."""
    return locale.split("_")[0] in _RTL_LOCALES


# ── Accessible label helper ────────────────────────────


def set_accessible_label(widget: Gtk.Widget, label: str) -> None:
    """Set a tooltip / accessible label for *widget*.

    This is picked up by screen readers (AT-SPI) on most desktops.
    """
    widget.set_tooltip_text(label)


# ── High-contrast CSS ──────────────────────────────────

_HIGH_CONTRAST_CSS = b"""
/* Strong focus outlines for keyboard & screen-reader users */
:focus-visible {
    outline: 2px solid @accent_color;
    outline-offset: 2px;
}

/* Ensure error banners have sufficient contrast */
.error-banner {
    background-color: alpha(@error_bg_color, 0.22);
    border-left: 4px solid @error_color;
}

/* Status indicator dot visibility */
.indicator-dot {
    border: 1px solid alpha(@view_fg_color, 0.1);
}
"""

_css_provider_installed = False


def apply_high_contrast_css() -> None:
    """Inject accessibility CSS into the application.

    Safe to call multiple times — only applies once.
    """
    global _css_provider_installed
    if _css_provider_installed:
        return

    provider = Gtk.CssProvider()
    provider.load_from_data(_HIGH_CONTRAST_CSS)

    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        _css_provider_installed = True


# ── Keyboard activation helper ─────────────────────────


def make_keyboard_activatable(widget: Gtk.Widget, callback: Callable[[], Any]) -> None:
    """Make *widget* activate *callback* on click or keyboard Enter/Space.

    For ``Gtk.Button`` this is the default.  This helper is useful for
    custom widgets that need both mouse and keyboard activation.
    """
    widget.set_focusable(True)
    if hasattr(widget, "connect"):
        widget.connect("activate", lambda *_: callback())
