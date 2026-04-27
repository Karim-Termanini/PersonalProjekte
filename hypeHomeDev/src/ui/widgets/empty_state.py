"""HypeDevHome — Empty state placeholder widget."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class EmptyState(Gtk.Box):
    """Placeholder shown when there is no content to display.

    Displays an icon, title, and optional description/action button.

    Parameters
    ----------
    icon_name : str
        Symbolic icon name.
    title : str
        Primary heading.
    description : str, optional
        Secondary explanatory text.
    button_label : str, optional
        Text for the optional action button.
    button_action : callable, optional
        Called when the action button is clicked.
    """

    def __init__(
        self,
        icon_name: str = "folder-symbolic",
        title: str = "Nothing here yet",
        description: str = "",
        button_label: str | None = None,
        button_action: Callable[..., Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_start=32,
            margin_end=32,
            margin_top=48,
            margin_bottom=48,
            **kwargs,
        )

        # Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(64)
        icon.set_opacity(0.5)
        self.append(icon)

        # Title
        title_lbl = Gtk.Label(label=title)
        title_lbl.add_css_class("title-2")
        self.append(title_lbl)

        # Description
        if description:
            desc = Gtk.Label(
                label=description,
                wrap=True,
                max_width_chars=40,
                justify=Gtk.Justification.CENTER,
            )
            desc.add_css_class("dim-label")
            self.append(desc)

        # Action button
        if button_label:
            btn = Gtk.Button(label=button_label)
            if button_action:
                btn.connect("clicked", lambda *_btn: button_action())
            self.append(btn)
