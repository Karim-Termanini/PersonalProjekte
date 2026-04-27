"""HypeDevHome — Card container widget."""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class Card(Gtk.Box):
    """A container with rounded corners, padding, and optional shadow.

    Wraps a single child widget inside a styled box following
    Libadwaita design patterns.

    Example
    -------
    >>> card = Card()
    >>> card.set_child(Gtk.Label(label="Hello"))
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
        )
        # Apply standard styles
        self.add_css_class("card")
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)

        # Apply remaining properties
        for key, value in kwargs.items():
            if hasattr(self, f"set_{key}"):
                getattr(self, f"set_{key}")(value)
            elif hasattr(self, key):
                setattr(self, key, value)
        self._child: Gtk.Widget | None = None

    def set_child(self, child: Gtk.Widget) -> None:
        """Set the card's content, replacing any existing child."""
        for old in list(self.observe_children()):
            self.remove(old)
        self.append(child)
        self._child = child

    def get_child(self) -> Gtk.Widget | None:
        return self._child
