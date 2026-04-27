"""HypeDevHome — Dashboard (main landing page).

Nordic redesign:
- System health status banner (HEALTHY / WARNING)
- Health metric cards: CPU / RAM / Disk / Uptime
- Quick actions: Tools → Servers, Tools → Install, Maintenance
- Widget grid (customisable, formerly a separate page)
Monitor data lives in Tools → Servers → Overview, NOT here.
"""

from __future__ import annotations

import logging
import threading

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.dashboard_grid import DashboardGrid  # noqa: E402
from ui.widgets.widget_gallery import WidgetGalleryDialog  # noqa: E402
from ui.widgets.workstation.nav_helper import navigate_workstation_section  # noqa: E402

log = logging.getLogger(__name__)


class DashboardPage(BasePage):
    """Main dashboard: health status + metric cards + widget grid."""

    page_title = "Dashboard"
    page_icon = "user-home-symbolic"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stats_timer_id: int = 0
        self._fetch_running: bool = False

        # Labels updated by background thread
        self._cpu_val: Gtk.Label | None = None
        self._mem_val: Gtk.Label | None = None
        self._disk_val: Gtk.Label | None = None
        self._uptime_val: Gtk.Label | None = None
        self._status_dot: Gtk.Label | None = None
        self._status_lbl: Gtk.Label | None = None

    # ── Build ────────────────────────────────────────────────────────

    def build_content(self) -> None:
        self.set_hexpand(True)
        self.set_vexpand(True)

        scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_valign(Gtk.Align.START)
        outer.set_margin_top(24)
        outer.set_margin_bottom(32)
        outer.set_margin_start(24)
        outer.set_margin_end(24)

        # 1. Status banner
        outer.append(self._build_status_banner())

        # 2. Metric cards
        outer.append(self._build_metric_cards())

        # 3. Quick actions
        outer.append(self._build_quick_actions())

        # 4. Widget grid
        widgets_hdr = Gtk.Label(label="WIDGETS")
        widgets_hdr.set_halign(Gtk.Align.START)
        widgets_hdr.set_margin_top(28)
        widgets_hdr.set_margin_bottom(12)
        widgets_hdr.add_css_class("section-title")
        outer.append(widgets_hdr)

        self._grid = DashboardGrid()
        outer.append(self._grid)

        scroll.set_child(outer)
        self.append(scroll)

    # ── Status banner ────────────────────────────────────────────────

    def _build_status_banner(self) -> Gtk.Widget:
        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        banner.add_css_class("dashboard-banner")
        banner.set_margin_bottom(20)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.set_hexpand(True)
        left.set_valign(Gtk.Align.CENTER)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        top_row.set_valign(Gtk.Align.CENTER)

        self._status_dot = Gtk.Label(label="●")
        self._status_dot.add_css_class("status-dot-healthy")
        top_row.append(self._status_dot)

        active_lbl = Gtk.Label(label="ACTIVE SYSTEM MONITORING")
        active_lbl.add_css_class("banner-eyebrow")
        top_row.append(active_lbl)

        left.append(top_row)

        self._status_lbl = Gtk.Label(label="HEALTHY")
        self._status_lbl.set_halign(Gtk.Align.START)
        self._status_lbl.add_css_class("banner-status")
        left.append(self._status_lbl)

        banner.append(left)
        return banner

    # ── Metric cards ─────────────────────────────────────────────────

    def _build_metric_cards(self) -> Gtk.Widget:
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(0)
        grid.set_column_homogeneous(True)
        grid.set_margin_bottom(4)

        self._cpu_val = Gtk.Label(label="—")
        self._mem_val = Gtk.Label(label="—")
        self._disk_val = Gtk.Label(label="—")
        self._uptime_val = Gtk.Label(label="—")

        grid.attach(self._metric_card("CPU LOAD", self._cpu_val), 0, 0, 1, 1)
        grid.attach(self._metric_card("MEMORY", self._mem_val), 1, 0, 1, 1)
        grid.attach(self._metric_card("DISK FREE", self._disk_val), 2, 0, 1, 1)
        grid.attach(self._metric_card("UPTIME", self._uptime_val), 3, 0, 1, 1)

        return grid

    def _metric_card(self, title: str, val_lbl: Gtk.Label) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("metric-card")
        card.set_hexpand(True)

        t = Gtk.Label(label=title)
        t.add_css_class("metric-card-title")
        t.set_halign(Gtk.Align.START)

        val_lbl.add_css_class("metric-card-value")
        val_lbl.set_halign(Gtk.Align.START)

        card.append(t)
        card.append(val_lbl)
        return card

    # ── Quick actions ────────────────────────────────────────────────

    def _build_quick_actions(self) -> Gtk.Widget:
        lbl = Gtk.Label(label="QUICK LINKS")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_top(20)
        lbl.set_margin_bottom(10)
        lbl.add_css_class("section-title")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        actions = [
            ("Servers & Docker", "network-server-symbolic",
             lambda *_: navigate_workstation_section("servers")),
            ("Install Tools", "folder-download-symbolic",
             lambda *_: navigate_workstation_section("install")),
            ("Config & dotfiles", "emblem-synchronizing-symbolic",
             lambda *_: navigate_workstation_section("config")),
            ("AI Tools", "preferences-desktop-accessibility-symbolic",
             lambda *_: navigate_workstation_section("ai")),
        ]
        for label, icon, handler in actions:
            btn = Gtk.Button()
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            content.set_margin_top(8)
            content.set_margin_bottom(8)
            content.set_margin_start(12)
            content.set_margin_end(12)
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(16)
            lbl_w = Gtk.Label(label=label)
            content.append(img)
            content.append(lbl_w)
            btn.set_child(content)
            btn.add_css_class("quick-link-btn")
            btn.set_hexpand(True)
            btn.connect("clicked", handler)
            row.append(btn)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.append(lbl)
        box.append(row)
        return box

    # ── Stats refresh ─────────────────────────────────────────────────

    def on_shown(self) -> None:
        super().on_shown()
        self._do_fetch()
        if not self._stats_timer_id:
            self._stats_timer_id = GLib.timeout_add_seconds(20, self._timer_tick)

    def on_hidden(self) -> None:
        super().on_hidden()
        if self._stats_timer_id:
            GLib.source_remove(self._stats_timer_id)
            self._stats_timer_id = 0

    def _timer_tick(self) -> bool:
        self._do_fetch()
        return True  # keep repeating

    def _do_fetch(self) -> None:
        if self._fetch_running:
            return
        self._fetch_running = True
        t = threading.Thread(target=self._fetch_worker, daemon=True)
        t.start()

    def _fetch_worker(self) -> None:
        """Runs in background thread — no GTK calls here."""
        try:
            from core.setup.host_executor import HostExecutor
            from ui.widgets.workstation.servers_overview import (
                _host_cpu_pct_between_samples,
                _parse_mem_pct,
            )

            ex = HostExecutor()
            cpu = _host_cpu_pct_between_samples(ex)
            _mem_pct, mem_str = _parse_mem_pct(ex)

            r = ex.run_sync(["df", "-h", "/"], timeout=5)
            disk_str = "—"
            if r.success and len(r.stdout.splitlines()) > 1:
                parts = r.stdout.splitlines()[1].split()
                if len(parts) > 3:
                    disk_str = f"{parts[3]} free"

            up = ex.run_sync(["uptime", "-p"], timeout=5)
            uptime_str = up.stdout.strip().removeprefix("up ") if up.success else "—"

            # Schedule GTK update on main thread
            GLib.idle_add(self._apply_stats, cpu, mem_str, disk_str, uptime_str)
        except Exception:
            log.exception("Dashboard stats fetch failed")
        finally:
            self._fetch_running = False

    def _apply_stats(self, cpu: float, mem: str, disk: str, uptime: str) -> None:
        """Called on main thread via GLib.idle_add."""
        if self._cpu_val:
            self._cpu_val.set_label(f"{cpu:.1f}%")
        if self._mem_val:
            self._mem_val.set_label(mem)
        if self._disk_val:
            self._disk_val.set_label(disk)
        if self._uptime_val:
            self._uptime_val.set_label(uptime)

        # Update status indicator based on CPU
        if self._status_dot and self._status_lbl:
            if cpu > 85:
                self._status_dot.remove_css_class("status-dot-healthy")
                self._status_dot.add_css_class("status-dot-warning")
                self._status_lbl.set_label("HIGH LOAD")
            else:
                self._status_dot.remove_css_class("status-dot-warning")
                self._status_dot.add_css_class("status-dot-healthy")
                self._status_lbl.set_label("HEALTHY")
        return False  # Required: GLib.idle_add callback must return False to run once

    # ── Header actions ────────────────────────────────────────────────

    def get_header_actions(self) -> list[Gtk.Widget]:
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.set_tooltip_text("Add Widget")
        add_btn.connect("clicked", self._on_add_widget)
        return [add_btn]

    def _on_add_widget(self, _btn: Gtk.Button) -> None:
        win = self.get_root()
        gallery = WidgetGalleryDialog(transient_for=win)
        gallery.set_selection_callback(self._on_widget_selected)
        gallery.present()

    def _on_widget_selected(self, widget_id: str) -> None:
        log.info("Adding widget: %s", widget_id)
        if hasattr(self, "_grid"):
            self._grid.add_widget_by_id(widget_id)
