"""HypeDevHome — Memory monitoring widget.

Displays RAM and swap usage with a circular progress indicator,
sparkline chart, and colour-coded warnings (≥85% / ≥95% RAM; swap pressure).
"""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402
from ui.widgets.chart import LineChart  # noqa: E402
from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402

log = logging.getLogger(__name__)


class MemoryWidget(DashboardWidget):
    """RAM + swap usage widget with live chart."""

    widget_title = "Memory Usage"
    widget_icon = "resource-monitor-memory-symbolic"
    widget_description = "Shows RAM and swap usage"
    widget_category = "System"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the memory widget."""
        self._history: list[float] = []
        self._max_history = 60
        self._used: float = 0
        self._total: float = 1
        self._ram_percent: float = 0.0
        self._swap_used: float = 0
        self._swap_total: float = 1
        self._swap_percent: float = 0.0

        super().__init__(
            widget_id="memory",
            title=self.widget_title,
            icon_name=self.widget_icon,
            refresh_interval=0.0,
            **kwargs,
        )

    def build_ui(self) -> None:
        """Build the memory widget's specific UI."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(8)

        # Main content row
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        # Left: progress
        self._progress = Gtk.ProgressBar()
        self._progress.set_halign(Gtk.Align.CENTER)
        self._progress.set_valign(Gtk.Align.CENTER)
        self._progress.set_size_request(120, -1)
        self._progress.set_show_text(True)
        row.append(self._progress)

        # Right: details
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        details.set_valign(Gtk.Align.CENTER)

        self._ram_label = Gtk.Label(label="RAM: — / —")
        self._ram_label.set_halign(Gtk.Align.START)
        details.append(self._ram_label)

        self._swap_label = Gtk.Label(label="Swap: — / —")
        self._swap_label.set_halign(Gtk.Align.START)
        self._swap_label.add_css_class("dim-label")
        details.append(self._swap_label)

        self._percent_label = Gtk.Label(label="0%")
        self._percent_label.set_halign(Gtk.Align.START)
        self._percent_label.add_css_class("title-2")
        details.append(self._percent_label)

        row.append(details)
        vbox.append(row)

        # Chart
        self._chart = LineChart(max_points=self._max_history, line_color="#e01b24")
        self._chart.set_size_request(-1, 60)
        vbox.append(self._chart)

        self.append(vbox)

    def on_activate(self) -> None:
        """Called when the widget is shown."""
        super().on_activate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.subscribe("sysmon.memory", self._on_memory_data)
            event_bus.subscribe("sysmon.swap", self._on_swap_data)

    def on_deactivate(self) -> None:
        """Called when the widget is removed."""
        super().on_deactivate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.unsubscribe("sysmon.memory", self._on_memory_data)
            event_bus.unsubscribe("sysmon.swap", self._on_swap_data)

    @staticmethod
    def _strip_warn_error(widget: Gtk.Widget) -> None:
        widget.remove_css_class("warning")
        widget.remove_css_class("error")

    def _on_memory_data(self, used: float, total: float, percent: float, **_kwargs: Any) -> None:
        """Handle incoming memory metrics."""
        self._used = used
        self._total = total
        self._ram_percent = float(percent)
        GLib.idle_add(self._update_ui)

    def _on_swap_data(
        self, used: float, total: float, percent: float = 0.0, **_kwargs: Any
    ) -> None:
        """Handle incoming swap metrics."""
        self._swap_used = used
        self._swap_total = total
        self._swap_percent = float(percent)
        GLib.idle_add(self._update_ui)

    def _apply_ram_style(self, pct: float) -> None:
        """Spec: warning ≥85%, critical ≥95%."""
        for w in (self._progress, self._percent_label, self._ram_label):
            self._strip_warn_error(w)
        if pct >= 95.0:
            for w in (self._progress, self._percent_label, self._ram_label):
                w.add_css_class("error")
        elif pct >= 85.0:
            for w in (self._progress, self._percent_label, self._ram_label):
                w.add_css_class("warning")

    def _apply_swap_style(self) -> None:
        """Highlight swap pressure when swap is in use."""
        self._strip_warn_error(self._swap_label)
        if self._swap_total <= 0:
            return
        sp = (
            (self._swap_used / self._swap_total) * 100.0
            if self._swap_total > 0
            else self._swap_percent
        )
        if sp >= 90.0:
            self._swap_label.add_css_class("error")
        elif sp >= 70.0:
            self._swap_label.add_css_class("warning")

    def _update_ui(self) -> None:
        """Update GTK widgets from current data."""
        pct = (self._used / self._total * 100.0) if self._total > 0 else 0.0
        if self._ram_percent > 0:
            pct = self._ram_percent

        def _mb(v: float) -> str:
            return f"{v / 1024:.1f} GB" if v >= 1024 else f"{v:.0f} MB"

        self._progress.set_fraction(self._used / self._total if self._total > 0 else 0)
        self._progress.set_text(f"{pct:.0f}%")
        self._percent_label.set_label(f"{pct:.0f}%")
        self._ram_label.set_label(f"RAM: {_mb(self._used)} / {_mb(self._total)}")
        self._swap_label.set_label(f"Swap: {_mb(self._swap_used)} / {_mb(self._swap_total)}")

        self._apply_ram_style(pct)
        self._apply_swap_style()

        # Chart
        self._history.append(pct)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self._chart.set_data(list(self._history))
