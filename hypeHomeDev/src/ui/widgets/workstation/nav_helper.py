"""Navigate the main window from embedded workstation widgets."""

from __future__ import annotations

import logging
from typing import Any, cast

from gi.repository import Gdk, GLib, Gtk

log = logging.getLogger(__name__)


def navigate_main_window(page_id: str) -> bool:
    """Switch the primary ``HypeDevHomeWindow`` to *page_id* if possible."""
    app = Gtk.Application.get_default()
    if not app:
        return False
    win = app.get_active_window()
    if win is None:
        return False
    nav = getattr(win, "navigate_to", None)
    if not callable(nav):
        log.debug("navigate_main_window: no navigate_to on %s", type(win).__name__)
        return False
    cast(Any, nav)(page_id)
    return True


def navigate_workstation_section(section_id: str) -> bool:
    """Open Workstation and switch to a sidebar subsection (e.g. ``ai``, ``servers``, ``services``)."""
    app = Gtk.Application.get_default()
    if app is None:
        return False
    win = app.get_active_window()
    if win is None:
        return False
    nav_ws = getattr(win, "navigate_to_workstation_section", None)
    if callable(nav_ws):
        return bool(nav_ws(section_id))
    return navigate_main_window("workstation")


def copy_plain_text_to_clipboard(text: str) -> bool:
    """Copy UTF-8 plain text to the default display clipboard. Returns False on failure."""
    try:
        display = Gdk.Display.get_default()
        if display is None:
            return False

        clip = display.get_clipboard()
        data = GLib.Bytes.new(text.encode("utf-8"))
        try:
            provider = Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8", data)
        except Exception:
            provider = Gdk.ContentProvider.new_for_value(GLib.Variant("s", text))
        clip.set_content(provider)
    except Exception:
        log.exception("copy_plain_text_to_clipboard failed")
        return False
    else:
        return True
