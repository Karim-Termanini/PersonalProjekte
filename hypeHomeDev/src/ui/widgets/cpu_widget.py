"""HypeDevHome — CPU monitoring widget.

Displays overall CPU usage, per-core utilization,
frequency, load average, and temperature.

This widget is a passive observer that subscribes to ``sysmon.cpu``
events from the SystemMonitor backend.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402
from ui.widgets.chart import LineChart  # noqa: E402
from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402

log = logging.getLogger(__name__)


class CPUWidget(DashboardWidget):
    """CPU usage widget with per-core bars and live chart.


    # Metadata for widget gallery
    widget_title = "CPU"
    widget_icon = "cpu-symbolic"
    widget_description = "Shows CPU usage and temperature"
    widget_category = "System"
    Subscribes to ``sysmon.cpu`` EventBus events from the
    SystemMonitor backend.
    """

    widget_title = "CPU Usage"
    widget_icon = "cpu-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the CPU widget."""
        # Initialize data before super().__init__ because it calls build_ui()
        self._total_percent: float = 0
        self._core_percents: list[float] = []
        self._frequency_mhz: float = 0
        self._load_avg: tuple[float, float, float] = (0, 0, 0)
        self._temperature_c: float | None = None
        self._history: list[float] = []
        self._max_history = 60
        self._show_temperature: bool = True
        self._show_frequency: bool = True
        self._show_load_avg: bool = True
        self._show_per_core: bool = True

        super().__init__(
            widget_id="cpu",
            title=self.widget_title,
            icon_name=self.widget_icon,
            refresh_interval=0.0,
            **kwargs,
        )

    def build_ui(self) -> None:
        """Build the CPU widget's specific UI."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(8)

        # Main stats row
        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        # Left: large percentage
        percent_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._percent_label = Gtk.Label(label="0%")
        self._percent_label.add_css_class("title-1")
        self._percent_label.set_halign(Gtk.Align.CENTER)
        percent_box.append(self._percent_label)

        self._freq_label = Gtk.Label(label="— GHz")
        self._freq_label.add_css_class("dim-label")
        self._freq_label.set_halign(Gtk.Align.CENTER)
        percent_box.append(self._freq_label)

        stats_row.append(percent_box)

        # Right: load averages
        load_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        load_box.set_valign(Gtk.Align.CENTER)

        self._load_label = Gtk.Label(label="Load: —, —, —")
        self._load_label.set_halign(Gtk.Align.START)
        load_box.append(self._load_label)

        self._temp_label = Gtk.Label(label="Temp: —°C")
        self._temp_label.set_halign(Gtk.Align.START)
        self._temp_label.add_css_class("dim-label")
        load_box.append(self._temp_label)

        stats_row.append(load_box)
        vbox.append(stats_row)

        # Per-core bars
        self._cores_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self._cores_box.set_margin_top(8)
        self._cores_box.set_margin_bottom(8)
        vbox.append(self._cores_box)

        # Chart
        self._chart = LineChart(max_points=self._max_history, line_color="#1c71d8")
        self._chart.set_size_request(-1, 60)
        vbox.append(self._chart)

        self.append(vbox)

    def on_activate(self) -> None:
        """Called when the widget is shown on the dashboard."""
        super().on_activate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.subscribe("sysmon.cpu", self._on_cpu_data)
        else:
            log.warning("EventBus not available for CPUWidget")

    def on_deactivate(self) -> None:
        """Called when the widget is removed or app closes."""
        super().on_deactivate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.unsubscribe("sysmon.cpu", self._on_cpu_data)

    def _on_cpu_data(
        self,
        total_percent: float = 0,
        core_percents: list[float] | None = None,
        core_count: int = 0,
        frequency_mhz: float = 0,
        load_avg: tuple[float, float, float] | None = None,
        temperature_c: float | None = None,
        **_kwargs: Any,
    ) -> None:
        """Called via EventBus with fresh CPU data."""
        self._total_percent = total_percent
        self._core_percents = core_percents or []
        self._frequency_mhz = frequency_mhz
        self._load_avg = load_avg or (0, 0, 0)
        self._temperature_c = temperature_c

        GLib.idle_add(self._update_ui)

    def _update_ui(self) -> None:
        """Update GTK widgets from current data."""
        # Update percentage
        self._percent_label.set_label(f"{self._total_percent:.0f}%")

        # Update frequency (if enabled)
        if self._show_frequency and self._frequency_mhz > 0:
            self._freq_label.set_label(f"{self._frequency_mhz / 1000:.1f} GHz")
            self._freq_label.show()
        else:
            self._freq_label.hide()

        # Update load averages (if enabled)
        if self._show_load_avg:
            load_str = (
                f"Load: {self._load_avg[0]:.2f}, {self._load_avg[1]:.2f}, {self._load_avg[2]:.2f}"
            )
            self._load_label.set_label(load_str)
            self._load_label.show()
        else:
            self._load_label.hide()

        # Update temperature (if enabled)
        if self._show_temperature and self._temperature_c is not None:
            self._temp_label.set_label(f"Temp: {self._temperature_c:.0f}°C")
            self._temp_label.show()
        else:
            self._temp_label.hide()

        # Colour warning
        if self._total_percent > 90:
            self._percent_label.add_css_class("error")
            self._percent_label.remove_css_class("warning")
        elif self._total_percent > 80:
            self._percent_label.add_css_class("warning")
            self._percent_label.remove_css_class("error")
        else:
            self._percent_label.remove_css_class("warning")
            self._percent_label.remove_css_class("error")

        # Update per-core bars (if enabled)
        if self._show_per_core:
            self._update_core_bars()
            self._cores_box.show()
        else:
            self._cores_box.hide()

        # Update chart
        self._history.append(self._total_percent)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        self._chart.set_data(list(self._history))

    def show_settings_dialog(self) -> None:
        """Show custom settings dialog for CPU widget."""

        dialog = Adw.PreferencesDialog(
            title=f"{self.title} Settings",
        )
        # Settings dialog in Libadwaita 1.4+ is presented via present(parent)
        root = self.get_root()
        parent = cast(Gtk.Window, root) if isinstance(root, Gtk.Window) else None

        # General page (from parent)
        # We don't call super here to avoid creating double dialogs
        # instead we build our specific pages.

        # CPU-specific page
        page = Adw.PreferencesPage()
        page.set_title("CPU Settings")
        dialog.add(page)

        # Display settings group
        display_group = Adw.PreferencesGroup(
            title="Display Options", description="Choose what information to show"
        )
        page.add(display_group)

        # Show temperature toggle
        temp_row = Adw.ActionRow(
            title="Show temperature", subtitle="Display CPU temperature if available"
        )
        temp_switch = Gtk.Switch()
        temp_switch.set_active(self._show_temperature)
        temp_switch.set_valign(Gtk.Align.CENTER)
        temp_switch.set_vexpand(False)
        temp_switch.connect("state-set", self._on_temperature_toggled)
        temp_row.add_suffix(temp_switch)
        display_group.add(temp_row)

        # Show frequency toggle
        freq_row = Adw.ActionRow(title="Show frequency", subtitle="Display current CPU frequency")
        freq_switch = Gtk.Switch()
        freq_switch.set_active(self._show_frequency)
        freq_switch.set_valign(Gtk.Align.CENTER)
        freq_switch.set_vexpand(False)
        freq_switch.connect("state-set", self._on_frequency_toggled)
        freq_row.add_suffix(freq_switch)
        display_group.add(freq_row)

        # Show load average toggle
        load_row = Adw.ActionRow(
            title="Show load average", subtitle="Display 1, 5, 15 minute load averages"
        )
        load_switch = Gtk.Switch()
        load_switch.set_active(self._show_load_avg)
        load_switch.set_valign(Gtk.Align.CENTER)
        load_switch.set_vexpand(False)
        load_switch.connect("state-set", self._on_load_avg_toggled)
        load_row.add_suffix(load_switch)
        display_group.add(load_row)

        # Show per-core bars toggle
        core_row = Adw.ActionRow(
            title="Show per-core usage", subtitle="Display individual core utilization bars"
        )
        core_switch = Gtk.Switch()
        core_switch.set_active(self._show_per_core)
        core_switch.set_valign(Gtk.Align.CENTER)
        core_switch.set_vexpand(False)
        core_switch.connect("state-set", self._on_per_core_toggled)
        core_row.add_suffix(core_switch)
        display_group.add(core_row)

        # Chart settings group
        chart_group = Adw.PreferencesGroup(
            title="Chart Settings", description="Configure history chart"
        )
        page.add(chart_group)

        # History length
        history_row = Adw.SpinRow(
            title="History length",
            subtitle="Number of data points to keep in chart",
            adjustment=Gtk.Adjustment(
                value=self._max_history,
                lower=10,
                upper=300,
                step_increment=10,
                page_increment=50,
            ),
        )
        history_row.connect("changed", self._on_history_length_changed)
        chart_group.add(history_row)

        dialog.present(parent)

    def _on_temperature_toggled(self, switch: Gtk.Switch, state: bool) -> None:
        """Handle temperature display toggle."""
        self._show_temperature = state
        self._update_ui()

    def _on_frequency_toggled(self, switch: Gtk.Switch, state: bool) -> None:
        """Handle frequency display toggle."""
        self._show_frequency = state
        self._update_ui()

    def _on_load_avg_toggled(self, switch: Gtk.Switch, state: bool) -> None:
        """Handle load average display toggle."""
        self._show_load_avg = state
        self._update_ui()

    def _on_per_core_toggled(self, switch: Gtk.Switch, state: bool) -> None:
        """Handle per-core display toggle."""
        self._show_per_core = state
        self._update_ui()

    def _on_history_length_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle history length change."""
        new_length = int(spin_row.get_value())
        if new_length != self._max_history:
            self._max_history = new_length
            # Trim history if needed
            if len(self._history) > new_length:
                self._history = self._history[-new_length:]
            self._chart.max_points = new_length

    def get_config(self) -> dict[str, Any]:
        """Return the current widget configuration for persistence."""
        config = super().get_config()
        config.update(
            {
                "show_temperature": self._show_temperature,
                "show_frequency": self._show_frequency,
                "show_load_avg": self._show_load_avg,
                "show_per_core": self._show_per_core,
                "max_history": self._max_history,
            }
        )
        return config

    def _update_core_bars(self) -> None:
        """Update the per-core progress bars."""
        # Clear existing bars
        child = self._cores_box.get_first_child()
        while child:
            self._cores_box.remove(child)
            child = self._cores_box.get_first_child()

        # Add new bars
        for i, percent in enumerate(self._core_percents):
            bar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            bar_box.set_valign(Gtk.Align.END)

            # Core label
            core_label = Gtk.Label(label=f"C{i}")
            core_label.add_css_class("caption")
            core_label.set_halign(Gtk.Align.CENTER)
            bar_box.append(core_label)

            # Progress bar
            bar = Gtk.ProgressBar()
            bar.set_fraction(percent / 100)
            bar.set_orientation(Gtk.Orientation.VERTICAL)
            bar.set_inverted(True)
            bar.set_size_request(12, 40)

            # Color coding
            if percent > 90:
                bar.add_css_class("error")
            elif percent > 80:
                bar.add_css_class("warning")

            bar_box.append(bar)
            self._cores_box.append(bar_box)
