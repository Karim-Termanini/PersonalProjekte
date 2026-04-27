"""HypeDevHome — Example Clock Widget for Dashboard Framework testing."""

from __future__ import annotations

import time
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402


class ClockWidget(DashboardWidget):
    """A simple clock widget to demonstrate the dashboard framework."""

    # Metadata for widget gallery
    widget_title = "Clock"
    widget_icon = "clock-symbolic"
    widget_description = "Shows current time"
    widget_category = "Utilities"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            widget_id="clock",
            title="System Clock",
            icon_name="preferences-system-time-symbolic",
            refresh_interval=1.0,
            **kwargs,
        )

    def build_ui(self) -> None:
        self._time_label = Gtk.Label()
        self._time_label.add_css_class("title-1")
        self._time_label.set_margin_top(20)
        self._time_label.set_margin_bottom(20)
        self.append(self._time_label)
        self._update_time()

    def refresh(self) -> bool:
        self._update_time()
        return True

    def _update_time(self) -> None:
        current_time = time.strftime("%H:%M:%S")
        self._time_label.set_label(current_time)
