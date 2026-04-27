"""HypeDevHome — Loading spinner widget."""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


class LoadingSpinner(Gtk.Box):
    """Centered spinner with optional label, used during async operations.

    Call :meth:`start` and :meth:`stop` to control the animation.

    Parameters
    ----------
    label : str, optional
        Descriptive text shown below the spinner.
    """

    def __init__(self, label: str = "Loading…", **kwargs: Any) -> None:
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            **kwargs,
        )

        self._spinner = Gtk.Spinner()
        self._spinner.set_size_request(36, 36)
        self.append(self._spinner)

        if label:
            lbl = Gtk.Label(
                label=label,
                css_classes=["dim-label"],
                wrap=True,
                max_width_chars=40,
            )
            self.append(lbl)

    def start(self) -> None:
        """Start the animation."""
        self._spinner.start()

    def stop(self) -> None:
        """Stop the animation."""
        self._spinner.stop()

    @property
    def is_spinning(self) -> bool:
        return bool(self._spinner.get_spinning())
