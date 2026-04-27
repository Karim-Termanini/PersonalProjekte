"""Scroll Learn cheatsheet panes so search hits are visible (GTK4 + subsection ScrolledWindow)."""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

# Vibrant palette for Learn section titles (dark-mode friendly, diverse hues)
_LEARN_TITLE_PALETTE = (
    "#ff9f43",  # warm orange
    "#0abde3",  # cyan
    "#ee5a24",  # red-orange
    "#10ac84",  # emerald
    "#f368e0",  # pink
    "#feca57",  # golden yellow
    "#ff6b6b",  # coral
    "#48dbfb",  # sky blue
    "#1dd1a1",  # mint
    "#c44569",  # berry
)


def learn_colored_title(text: str, index: int) -> str:
    """Wrap *text* in Pango markup with a color from the Learn palette.

    Use as the `title` argument for ``Adw.PreferencesGroup`` —
    Libadwaita title labels interpret Pango markup by default.
    """
    if not text:
        return text
    color = _LEARN_TITLE_PALETTE[index % len(_LEARN_TITLE_PALETTE)]
    safe = GLib.markup_escape_text(text)
    return f'<span foreground="{color}" weight="bold">{safe}</span>'


def _find_scrolled_window(widget: Gtk.Widget) -> Gtk.ScrolledWindow | None:
    w: Gtk.Widget | None = widget
    while w is not None:
        parent = w.get_parent()
        if isinstance(parent, Gtk.ScrolledWindow):
            return parent
        w = parent
    return None


def _scroll_scrolled_window_to_top(start: Gtk.Widget) -> None:
    sw = _find_scrolled_window(start)
    if sw is None:
        return
    sw.get_vadjustment().set_value(0.0)


def _scroll_widget_into_viewport(widget: Gtk.Widget) -> bool:
    """Return True if bounds were usable and scroll value was set."""
    w: Gtk.Widget | None = widget
    while w is not None:
        parent = w.get_parent()
        if isinstance(parent, Gtk.ScrolledWindow):
            sw = parent
            scroll_child = sw.get_child()
            if scroll_child is None:
                return False
            ok, rect = widget.compute_bounds(scroll_child)
            if not ok or rect is None:
                return False
            oy = float(rect.origin.y)
            sh = float(rect.size.height)
            sw_w = float(rect.size.width)
            if sh <= 1.0 and sw_w <= 1.0:
                return False
            adj = sw.get_vadjustment()
            page = adj.get_page_size()
            upper = adj.get_upper()
            margin = 8.0
            target = max(0.0, oy - margin)
            target = min(target, max(0.0, upper - page))
            adj.set_value(target)
            return True
        w = parent
    return False


def schedule_scroll_widget_into_view(widget: Gtk.Widget) -> None:
    """Defer until after layout; retry once if allocations were not ready."""

    def _idle() -> None:
        if _scroll_widget_into_viewport(widget):
            return

        def _retry() -> bool:
            _scroll_widget_into_viewport(widget)
            return False

        GLib.timeout_add(100, _retry)

    GLib.idle_add(_idle)


def scroll_learn_search_to_first_hit(
    search_targets: list[tuple[Gtk.Revealer, Any, ...]],
    *,
    has_query: bool,
) -> None:
    """After filtering, scroll so the first visible block is in view (or top if query cleared)."""
    if not search_targets:
        return
    first = search_targets[0][0]
    if not has_query:
        _scroll_scrolled_window_to_top(first)
        return
    for row in search_targets:
        revealer = row[0]
        if revealer.get_reveal_child():
            schedule_scroll_widget_into_view(revealer)
            return
    _scroll_scrolled_window_to_top(first)
