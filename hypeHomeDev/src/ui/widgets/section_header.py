"""HypeDevHome — Section header widget."""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class SectionHeader(Gtk.Box):
    """Consistent section header with title and optional subtitle.

    Parameters
    ----------
    title : str
        Section heading text.
    subtitle : str, optional
        Smaller description text below the title.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        **kwargs: Any,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=2,
            margin_start=12,
            margin_end=12,
            margin_top=12,
            margin_bottom=6,
            **kwargs,
        )

        # Title
        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("title-3")
        title_lbl.set_halign(Gtk.Align.START)
        self.append(title_lbl)

        # Subtitle
        if subtitle:
            sub = Gtk.Label(label=subtitle)
            sub.add_css_class("dim-label")
            sub.set_halign(Gtk.Align.START)
            self.append(sub)
