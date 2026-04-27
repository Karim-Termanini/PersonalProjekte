"""HypeDevHome — Network monitoring widget.

Displays real-time download/upload speeds, interface selection,
local and public IP, peaks, cumulative totals, and a live speed graph.
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
from ui.widgets.status_indicator import StatusIndicator, StatusLevel  # noqa: E402

log = logging.getLogger(__name__)


def _fmt_bytes(n: float) -> str:
    if n >= 1024**4:
        return f"{n / 1024**4:.2f} TB"
    if n >= 1024**3:
        return f"{n / 1024**3:.2f} GB"
    if n >= 1024**2:
        return f"{n / 1024**2:.1f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n:.0f} B"


class NetworkWidget(DashboardWidget):
    """Real-time network speed widget."""

    widget_title = "Network Traffic"
    widget_icon = "network-transmit-receive-symbolic"
    widget_description = "Shows network speed, IPs, peaks, and interface selection"
    widget_category = "System"

    def __init__(self, **kwargs: Any) -> None:
        self._selected_iface = str(kwargs.pop("network_interface", "all"))
        self._dl_speed: float = 0.0
        self._ul_speed: float = 0.0
        self._peak_dl: float = 0.0
        self._peak_ul: float = 0.0
        self._local_ip: str = "—"
        self._public_ip: str = ""
        self._connected: bool = False
        self._dl_history: list[float] = []
        self._max_history = 60
        self._last_event: dict[str, Any] = {}
        self._iface_dropdown: Gtk.DropDown | None = None
        self._rebuilding_dropdown = False

        super().__init__(
            widget_id="network",
            title=self.widget_title,
            icon_name=self.widget_icon,
            refresh_interval=0.0,
            **kwargs,
        )

    def build_ui(self) -> None:
        """Build the network widget's specific UI."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(8)

        # Status row
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._status_dot = StatusIndicator(level=StatusLevel.NEUTRAL, label="Checking…")
        status_row.append(self._status_dot)

        iface_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        iface_label = Gtk.Label(label="Interface:")
        iface_label.add_css_class("caption")
        iface_label.set_halign(Gtk.Align.START)
        iface_row.append(iface_label)

        self._iface_dropdown = Gtk.DropDown()
        self._iface_dropdown.set_hexpand(True)
        self._iface_dropdown.set_model(Gtk.StringList.new(["All interfaces"]))
        self._iface_dropdown.connect("notify::selected", self._on_iface_selected)
        iface_row.append(self._iface_dropdown)

        vbox.append(status_row)
        vbox.append(iface_row)

        # IPs
        ip_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._local_ip_label = Gtk.Label(label="Local: —")
        self._local_ip_label.set_halign(Gtk.Align.START)
        self._local_ip_label.add_css_class("dim-label")
        self._local_ip_label.set_wrap(True)
        ip_row.append(self._local_ip_label)

        self._public_ip_label = Gtk.Label(label="Public: —")
        self._public_ip_label.set_halign(Gtk.Align.START)
        self._public_ip_label.add_css_class("dim-label")
        self._public_ip_label.set_wrap(True)
        ip_row.append(self._public_ip_label)

        vbox.append(ip_row)

        # Speed display row
        speed_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)

        dl_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        dl_box.set_hexpand(True)
        self._dl_label = Gtk.Label(label="↓ —")
        self._dl_label.add_css_class("title-2")
        dl_box.append(self._dl_label)
        speed_row.append(dl_box)

        ul_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ul_box.set_hexpand(True)
        self._ul_label = Gtk.Label(label="↑ —")
        self._ul_label.add_css_class("title-2")
        ul_box.append(self._ul_label)
        speed_row.append(ul_box)

        vbox.append(speed_row)

        # Peaks & totals (since boot — kernel counters)
        meta_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self._peak_label = Gtk.Label(label="Peak: ↓ — · ↑ —")
        self._peak_label.set_halign(Gtk.Align.START)
        self._peak_label.add_css_class("caption")
        self._peak_label.add_css_class("dim-label")
        meta_row.append(self._peak_label)

        self._total_label = Gtk.Label(label="Totals (since boot): ↓ — · ↑ —")
        self._total_label.set_halign(Gtk.Align.START)
        self._total_label.add_css_class("caption")
        self._total_label.add_css_class("dim-label")
        meta_row.append(self._total_label)

        vbox.append(meta_row)

        self._chart = LineChart(max_points=self._max_history, line_color="#26a269")
        self._chart.set_size_request(-1, 60)
        vbox.append(self._chart)

        self.append(vbox)

    def get_config(self) -> dict[str, Any]:
        cfg = super().get_config()
        cfg["network_interface"] = self._selected_iface
        return cfg

    def on_activate(self) -> None:
        """Called when the widget is shown."""
        super().on_activate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.subscribe("sysmon.network", self._on_network_data)

    def on_deactivate(self) -> None:
        """Called when the widget is removed."""
        super().on_deactivate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.unsubscribe("sysmon.network", self._on_network_data)

    def _on_iface_selected(self, dropdown: Gtk.DropDown, _pspec: Any) -> None:
        if self._rebuilding_dropdown:
            return
        model = dropdown.get_model()
        if not model:
            return
        idx = dropdown.get_selected()
        if idx == Gtk.INVALID_LIST_POSITION:
            return
        item = model.get_item(idx)
        text = item.get_string() if item is not None else ""  # type: ignore[union-attr]
        new_sel = "all" if text == "All interfaces" else text
        if new_sel != self._selected_iface:
            self._peak_dl = 0.0
            self._peak_ul = 0.0
        self._selected_iface = new_sel
        if self._last_event:
            GLib.idle_add(self._update_ui)

    def _on_network_data(self, **kwargs: Any) -> None:
        """Handle incoming network metrics."""
        self._last_event = dict(kwargs)

        self._connected = bool(kwargs.get("connected", False))
        self._public_ip = str(kwargs.get("public_ip") or "")

        if_list = kwargs.get("interfaces") or []
        self._rebuild_iface_dropdown_if_needed(if_list)

        dl, ul, local_ip = self._extract_display_speeds(kwargs)
        self._dl_speed = dl
        self._ul_speed = ul
        self._local_ip = local_ip or "—"

        if dl > self._peak_dl:
            self._peak_dl = dl
        if ul > self._peak_ul:
            self._peak_ul = ul

        GLib.idle_add(self._update_ui)

    def _extract_display_speeds(self, payload: dict[str, Any]) -> tuple[float, float, str]:
        """Pick speeds and primary local IP for current interface selection."""
        per_nic = payload.get("per_nic") or {}
        if self._selected_iface == "all":
            dl = float(payload.get("dl_speed") or 0.0)
            ul = float(payload.get("ul_speed") or 0.0)
            return dl, ul, str(payload.get("local_ip") or "")

        entry = per_nic.get(self._selected_iface)
        if isinstance(entry, dict):
            dl = float(entry.get("dl_speed") or 0.0)
            ul = float(entry.get("ul_speed") or 0.0)
            lip = str(entry.get("ipv4") or "")
            return dl, ul, lip
        return 0.0, 0.0, ""

    def _extract_display_totals(self, payload: dict[str, Any]) -> tuple[float, float]:
        """Return cumulative recv/sent bytes for selection (since boot)."""
        per_nic = payload.get("per_nic") or {}
        if self._selected_iface == "all":
            return float(payload.get("dl_bytes") or 0), float(payload.get("ul_bytes") or 0)
        entry = per_nic.get(self._selected_iface)
        if isinstance(entry, dict):
            return float(entry.get("bytes_recv") or 0), float(entry.get("bytes_sent") or 0)
        return 0.0, 0.0

    def _rebuild_iface_dropdown_if_needed(self, interfaces: list[dict[str, Any]]) -> None:
        """Refresh dropdown when interface list from the host changes."""
        names: list[str] = [str(n) for n in (x.get("name") for x in interfaces) if n]
        if not self._iface_dropdown:
            return
        model = self._iface_dropdown.get_model()
        current = []
        if model:
            for i in range(model.get_n_items()):
                it = model.get_item(i)
                if it is not None:
                    current.append(it.get_string())  # type: ignore[union-attr]
        new_list = ["All interfaces", *names]
        if current == new_list:
            return

        self._rebuilding_dropdown = True
        try:
            self._iface_dropdown.set_model(Gtk.StringList.new(new_list))
            # Restore selection
            if self._selected_iface == "all":
                self._iface_dropdown.set_selected(0)
            elif self._selected_iface in names:
                self._iface_dropdown.set_selected(1 + names.index(self._selected_iface))
            else:
                self._iface_dropdown.set_selected(0)
                self._selected_iface = "all"
        finally:
            self._rebuilding_dropdown = False

    def _update_ui(self) -> None:
        """Update GTK widgets from current data."""

        def fmt_speed(bps: float) -> str:
            if bps >= 1024 * 1024:
                return f"{bps / (1024 * 1024):.1f} MB/s"
            if bps >= 1024:
                return f"{bps / 1024:.1f} KB/s"
            return f"{bps:.0f} B/s"

        self._dl_label.set_label(f"↓ {fmt_speed(self._dl_speed)}")
        self._ul_label.set_label(f"↑ {fmt_speed(self._ul_speed)}")

        if self._selected_iface == "all":
            loc = self._local_ip
            self._local_ip_label.set_label(f"Local (default route): {loc}")
        else:
            self._local_ip_label.set_label(f"Local ({self._selected_iface}): {self._local_ip}")

        if self._public_ip:
            self._public_ip_label.set_label(f"Public: {self._public_ip}")
        else:
            self._public_ip_label.set_label(
                "Public: —" if self._connected else "Public: (offline)"
            )

        if self._connected:
            self._status_dot.level = StatusLevel.SUCCESS
            self._status_dot.label_text = "Connected"
        else:
            self._status_dot.level = StatusLevel.ERROR
            self._status_dot.label_text = "No link"

        self._peak_label.set_label(
            f"Peak (this session): ↓ {fmt_speed(self._peak_dl)} · ↑ {fmt_speed(self._peak_ul)}"
        )

        br, bs = self._extract_display_totals(self._last_event)
        self._total_label.set_label(
            f"Totals (since boot): ↓ {_fmt_bytes(br)} · ↑ {_fmt_bytes(bs)}"
        )

        self._dl_history.append(self._dl_speed)
        if len(self._dl_history) > self._max_history:
            self._dl_history.pop(0)
        self._chart.set_data(list(self._dl_history))
