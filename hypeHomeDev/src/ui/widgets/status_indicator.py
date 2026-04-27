"""HypeDevHome — Status indicator widget."""

from __future__ import annotations

from enum import Enum
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402


class StatusLevel(Enum):
    """Semantic status levels mapped to colors."""

    SUCCESS = "#26a269"
    WARNING = "#f5c211"
    ERROR = "#e01b24"
    INFO = "#3584e4"
    NEUTRAL = "#9a9996"


class StatusIndicator(Gtk.Box):
    """A small colored dot with an optional label.

    The dot color corresponds to the semantic status level.

    Example
    -------
    >>> indicator = StatusIndicator(StatusLevel.SUCCESS, label="Connected")
    """

    def __init__(
        self,
        level: StatusLevel = StatusLevel.NEUTRAL,
        label: str | None = None,
        size: int = 10,
        **kwargs: Any,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, **kwargs)
        self._level = level
        self._size = size

        self._dot = Gtk.Box(
            css_classes=["indicator-dot"],
            width_request=size,
            height_request=size,
            margin_start=4,
        )
        self._apply_color()
        self.append(self._dot)

        if label:
            self._label = Gtk.Label(
                label=label,
                halign=Gtk.Align.START,
                css_classes=["caption"],
            )
            self.append(self._label)

    @property
    def level(self) -> StatusLevel:
        return self._level

    @level.setter
    def level(self, value: StatusLevel) -> None:
        self._level = value
        self._apply_color()

    @property
    def label_text(self) -> str | None:
        return self._label.get_label() if hasattr(self, "_label") else None

    @label_text.setter
    def label_text(self, value: str | None) -> None:
        if hasattr(self, "_label"):
            self._label.set_label(value or "")

    def _apply_color(self) -> None:
        css = (
            f".indicator-dot {{ background-color: {self._level.value}; "
            f"border-radius: {self._size // 2}px; "
            f"min-width: {self._size}px; "
            f"min-height: {self._size}px; }}"
        )
        provider = Gtk.CssProvider()
        provider.load_from_string(css)
        display = Gdk.Display.get_default()
        if display:
            Gtk.StyleContext.add_provider_for_display(
                display,
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
            )
        self._dot.add_css_class("indicator-dot")
