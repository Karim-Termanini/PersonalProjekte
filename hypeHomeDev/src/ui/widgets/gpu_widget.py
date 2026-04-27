"""HypeDevHome — GPU monitoring widget.

Displays GPU utilization, VRAM usage, temperature,
and vendor-specific information.

This widget is a passive observer that subscribes to ``sysmon.gpu``
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
from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402

log = logging.getLogger(__name__)


class GPUWidget(DashboardWidget):
    """GPU monitoring widget with vendor detection.

    Subscribes to ``sysmon.gpu`` EventBus events from the
    SystemMonitor backend.

    Metadata for widget gallery
    widget_title = "GPU"
    widget_icon = "gpu-symbolic"
    widget_description = "Shows GPU usage and temperature"
    widget_category = "System"
    Supports NVIDIA (nvidia-smi), AMD (sysfs), and Intel (sysfs).
    Falls back to generic detection when specific tools are unavailable.
    """

    widget_title = "GPU"
    widget_icon = "video-display-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the GPU widget."""
        self._gpu_index: int = max(0, int(kwargs.pop("gpu_index", 0)))
        self._gpus_list: list[dict[str, Any]] = []
        self._rebuilding_gpu_dropdown = False

        # Initialize data before super().__init__ because it calls build_ui()
        self._vendor: str = "Unknown"
        self._model: str = "Unknown"
        self._utilization: float = 0
        self._vram_used: float = 0
        self._vram_total: float = 1
        self._temperature: float | None = None
        self._fan_speed: float | None = None
        self._detected: bool = False

        # UI Toggles (Agent A stabilization)
        self._show_temperature: bool = kwargs.get("show_temperature", True)
        self._show_fan_speed: bool = kwargs.get("show_fan_speed", True)

        super().__init__(
            widget_id="gpu",
            title=self.widget_title,
            icon_name=self.widget_icon,
            refresh_interval=0.0,
            **kwargs,
        )

    def build_ui(self) -> None:
        """Build the GPU widget's specific UI."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(8)

        self._gpu_dropdown = Gtk.DropDown()
        self._gpu_dropdown.set_hexpand(True)
        self._gpu_dropdown.set_model(Gtk.StringList.new(["GPU"]))
        self._gpu_dropdown.connect("notify::selected", self._on_gpu_dropdown_selected)
        self._gpu_dropdown.set_tooltip_text("Select GPU when multiple GPUs are present")
        self._gpu_dropdown.set_visible(False)
        vbox.append(self._gpu_dropdown)

        # Vendor/model row
        self._vendor_label = Gtk.Label(label="Detecting GPU...")
        self._vendor_label.set_halign(Gtk.Align.START)
        self._vendor_label.add_css_class("heading")
        vbox.append(self._vendor_label)

        # Utilization row
        util_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        # Utilization progress bar
        util_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        util_label = Gtk.Label(label="Utilization")
        util_label.set_halign(Gtk.Align.START)
        util_label.add_css_class("caption")
        util_box.append(util_label)

        self._util_bar = Gtk.ProgressBar()
        self._util_bar.set_show_text(True)
        util_box.append(self._util_bar)

        util_row.append(util_box)

        # VRAM usage
        vram_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vram_label = Gtk.Label(label="VRAM")
        vram_label.set_halign(Gtk.Align.START)
        vram_label.add_css_class("caption")
        vram_box.append(vram_label)

        self._vram_bar = Gtk.ProgressBar()
        self._vram_bar.set_show_text(True)
        vram_box.append(self._vram_bar)

        util_row.append(vram_box)
        vbox.append(util_row)

        # Temperature and fan speed
        stats_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)

        self._temp_label = Gtk.Label(label="Temp: —°C")
        self._temp_label.set_halign(Gtk.Align.START)
        stats_row.append(self._temp_label)

        self._fan_label = Gtk.Label(label="Fan: —%")
        self._fan_label.set_halign(Gtk.Align.START)
        stats_row.append(self._fan_label)

        vbox.append(stats_row)

        self.append(vbox)

    def on_activate(self) -> None:
        """Called when the widget is shown on the dashboard."""
        super().on_activate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.subscribe("sysmon.gpu", self._on_gpu_data)
        else:
            log.warning("EventBus not available for GPUWidget")

    def on_deactivate(self) -> None:
        """Called when the widget is removed or app closes."""
        super().on_deactivate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.unsubscribe("sysmon.gpu", self._on_gpu_data)

    def _on_gpu_data(
        self,
        vendor: str = "Unknown",
        model: str = "Unknown",
        utilization: float = 0.0,
        vram_used: float = 0.0,
        vram_total: float = 1.0,
        temperature_c: float | None = None,
        fan_speed: float | None = None,
        detected: bool = False,
        gpus: list[dict[str, Any]] | None = None,
        gpu_count: int = 0,
        **_kwargs: Any,
    ) -> None:
        """Handle GPU data emitted by the system monitor."""
        if gpus:
            self._gpus_list = list(gpus)
            n = len(self._gpus_list)
            if n > 0:
                self._gpu_index = min(self._gpu_index, n - 1)
            self._rebuild_gpu_dropdown_model()
            self._apply_gpu_snapshot(self._gpus_list[self._gpu_index] if self._gpus_list else {})
        else:
            self._gpus_list = []
            self._gpu_dropdown.set_visible(False)
            self._vendor = vendor
            self._model = model
            self._utilization = utilization
            self._vram_used = vram_used
            self._vram_total = vram_total
            self._temperature = temperature_c
            self._fan_speed = fan_speed
            self._detected = detected
        GLib.idle_add(self._update_ui)

    def _apply_gpu_snapshot(self, g: dict[str, Any]) -> None:
        """Copy one GPU dict into display fields."""
        self._vendor = str(g.get("vendor", "Unknown"))
        self._model = str(g.get("model", "Unknown"))
        self._utilization = float(g.get("utilization", 0.0))
        self._vram_used = float(g.get("vram_used", 0.0))
        self._vram_total = float(g.get("vram_total", 1.0)) or 1.0
        tc = g.get("temperature_c")
        self._temperature = float(tc) if tc is not None else None
        fs = g.get("fan_speed")
        self._fan_speed = float(fs) if fs is not None else None
        self._detected = bool(g.get("detected", False))

    def _rebuild_gpu_dropdown_model(self) -> None:
        """Show dropdown when multiple GPUs; keep selection in sync."""
        if not self._gpu_dropdown:
            return
        n = len(self._gpus_list)
        if n <= 1:
            self._gpu_dropdown.set_visible(False)
            return
        labels: list[str] = []
        for i, g in enumerate(self._gpus_list):
            m = str(g.get("model", f"GPU {i}"))[:48]
            v = str(g.get("vendor", "?"))
            labels.append(f"{i}: {v} — {m}")
        self._rebuilding_gpu_dropdown = True
        try:
            self._gpu_dropdown.set_model(Gtk.StringList.new(labels))
            self._gpu_dropdown.set_selected(self._gpu_index)
            self._gpu_dropdown.set_visible(True)
        finally:
            self._rebuilding_gpu_dropdown = False

    def _on_gpu_dropdown_selected(self, _dd: Gtk.DropDown, _pspec: Any) -> None:
        if self._rebuilding_gpu_dropdown or not self._gpus_list:
            return
        idx = self._gpu_dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION:
            return
        if 0 <= idx < len(self._gpus_list):
            self._gpu_index = idx
            self._apply_gpu_snapshot(self._gpus_list[idx])
            self._update_ui()
            parent = self.get_parent()
            while parent and not hasattr(parent, "_update_state_from_layout"):
                parent = parent.get_parent()
            if parent and hasattr(parent, "_update_state_from_layout"):
                parent._update_state_from_layout()

    def _update_ui(self) -> None:
        """Update GTK widgets from current data."""
        if not self._detected:
            self._vendor_label.set_label("No GPU detected")
            return

        # Update vendor/model
        self._vendor_label.set_label(f"{self._vendor}: {self._model}")

        # Update utilization
        self._util_bar.set_fraction(self._utilization / 100)
        self._util_bar.set_text(f"{self._utilization:.0f}%")

        # Update VRAM
        if self._vram_total > 0:
            self._vram_bar.set_fraction(self._vram_used / self._vram_total)
            self._vram_bar.set_text(f"{self._vram_used:.0f}/{self._vram_total:.0f} MB")
        else:
            self._vram_bar.set_fraction(0)
            self._vram_bar.set_text("—")

        # Update temperature (if enabled)
        if self._show_temperature and self._temperature is not None:
            self._temp_label.set_label(f"Temp: {self._temperature:.0f}°C")
            self._temp_label.show()
            # Color coding for temperature
            if self._temperature > 85:
                self._temp_label.add_css_class("error")
                self._temp_label.remove_css_class("warning")
            elif self._temperature > 75:
                self._temp_label.add_css_class("warning")
                self._temp_label.remove_css_class("error")
            else:
                self._temp_label.remove_css_class("warning")
                self._temp_label.remove_css_class("error")
        else:
            self._temp_label.set_label("Temp: —°C")
            self._temp_label.hide()
            self._temp_label.remove_css_class("warning")
            self._temp_label.remove_css_class("error")

        # Update fan speed (if enabled)
        if self._show_fan_speed and self._fan_speed is not None:
            self._fan_label.set_label(f"Fan: {self._fan_speed:.0f}%")
            self._fan_label.show()
        else:
            self._fan_label.set_label("Fan: —%")
            self._fan_label.hide()

        # Color coding for utilization
        if self._utilization > 90:
            self._util_bar.add_css_class("error")
            self._util_bar.remove_css_class("warning")
        elif self._utilization > 80:
            self._util_bar.add_css_class("warning")
            self._util_bar.remove_css_class("error")
        else:
            self._util_bar.remove_css_class("warning")
            self._util_bar.remove_css_class("error")

        # We don't call super here to avoid creating double dialogs
        # instead we build our specific pages.

    def show_settings_dialog(self) -> None:
        """Show settings dialog for GPU widget."""

        dialog = Adw.PreferencesDialog(
            title=f"{self.title} Settings",
        )
        # Settings dialog in Libadwaita 1.4+ is presented via present(parent)
        root = self.get_root()
        parent = cast(Gtk.Window, root) if isinstance(root, Gtk.Window) else None

        # General page
        page = Adw.PreferencesPage()
        dialog.add(page)

        # Display settings group
        group = Adw.PreferencesGroup(
            title="Display Options", description="Choose what information to show"
        )
        page.add(group)

        # Temperature toggle
        temp_row = Adw.ActionRow(title="Show temperature")
        temp_switch = Gtk.Switch()
        temp_switch.set_active(self._show_temperature)
        temp_switch.connect("state-set", self._on_temperature_toggled)
        temp_row.add_suffix(temp_switch)
        group.add(temp_row)

        # Fan speed toggle
        fan_row = Adw.ActionRow(title="Show fan speed")
        fan_switch = Gtk.Switch()
        fan_switch.set_active(self._show_fan_speed)
        fan_switch.connect("state-set", self._on_fan_speed_toggled)
        fan_row.add_suffix(fan_switch)
        group.add(fan_row)

        dialog.present(parent)

    def _on_temperature_toggled(self, _switch: Gtk.Switch, state: bool) -> None:
        self._show_temperature = state
        self._update_ui()
        parent = self.get_parent()
        if parent and hasattr(parent, "_update_state_from_layout"):
            parent._update_state_from_layout()

    def _on_fan_speed_toggled(self, _switch: Gtk.Switch, state: bool) -> None:
        self._show_fan_speed = state
        self._update_ui()
        parent = self.get_parent()
        if parent and hasattr(parent, "_update_state_from_layout"):
            parent._update_state_from_layout()

    def get_config(self) -> dict[str, Any]:
        """Return the current widget configuration for persistence."""
        config = super().get_config()
        config.update(
            {
                "show_temperature": self._show_temperature,
                "show_fan_speed": self._show_fan_speed,
                "gpu_index": self._gpu_index,
            }
        )
        return config
