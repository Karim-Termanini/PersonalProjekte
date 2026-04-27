"""HypeDevHome — Dashboard (main landing page).

Layout:
  [SYSTEM HEALTH]
  ┌──────┬──────┬──────┬──────┐
  │ CPU  │ RAM  │ Disk │ Up   │  ← metric cards
  └──────┴──────┴──────┴──────┘

  [QUICK LINKS]
  Servers & Docker  |  Install  |  Config  |  AI

  [WIDGETS]
  DashboardGrid (has its own scroll + drag-drop)

The DashboardGrid has its OWN internal ScrolledWindow + vexpand.
This page must NOT wrap everything in an outer ScrolledWindow.
Instead: top section in a fixed Box, widget grid below with vexpand.
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

        self._cpu_val: Gtk.Label | None = None
        self._mem_val: Gtk.Label | None = None
        self._disk_val: Gtk.Label | None = None
        self._uptime_val: Gtk.Label | None = None
        self._status_lbl: Gtk.Label | None = None
        self._status_dot: Gtk.Label | None = None

    # ── Build ────────────────────────────────────────────────────────

    def build_content(self) -> None:
        # Root: vertical box — top section fixed, grid below expands.
        self.set_orientation(Gtk.Orientation.VERTICAL)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_spacing(0)

        # ── TOP SECTION (fixed height, no scroll) ─────────────────
        top = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        top.set_hexpand(True)
        top.set_vexpand(False)
        top.set_margin_top(0)
        top.set_margin_start(0)
        top.set_margin_end(0)
        top.set_margin_bottom(0)

        top.append(self._build_status_banner())
        top.append(self._build_metric_cards())
        top.append(self._build_quick_actions())

        # WIDGETS section title
        wgt_hdr = Gtk.Label(label="WIDGETS")
        wgt_hdr.set_halign(Gtk.Align.START)
        wgt_hdr.set_margin_top(20)
        wgt_hdr.set_margin_bottom(10)
        wgt_hdr.set_margin_start(20)
        wgt_hdr.add_css_class("section-title")
        top.append(wgt_hdr)

        self.append(top)

        # ── WIDGET GRID (expands to fill remaining space) ─────────
        # DashboardGrid already has its own internal ScrolledWindow + vexpand.
        self._grid = DashboardGrid()
        self._grid.set_margin_start(8)
        self._grid.set_margin_end(8)
        self._grid.set_margin_bottom(8)
        self.append(self._grid)

    # ── Status banner ────────────────────────────────────────────────

    def _build_status_banner(self) -> Gtk.Widget:
        banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        banner.add_css_class("dashboard-banner")
        banner.set_margin_bottom(16)

        # Left side: eyebrow + big status
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        left.set_hexpand(True)
        left.set_valign(Gtk.Align.CENTER)

        dot_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dot_row.set_valign(Gtk.Align.CENTER)

        self._status_dot = Gtk.Label(label="●")
        self._status_dot.add_css_class("status-dot-healthy")
        dot_row.append(self._status_dot)

        eye = Gtk.Label(label="ACTIVE SYSTEM MONITORING")
        eye.add_css_class("banner-eyebrow")
        dot_row.append(eye)

        left.append(dot_row)

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
        grid.set_margin_bottom(0)

        self._cpu_val = Gtk.Label(label="—")
        self._mem_val = Gtk.Label(label="—")
        self._disk_val = Gtk.Label(label="—")
        self._uptime_val = Gtk.Label(label="—")

        grid.attach(self._metric_card("CPU", self._cpu_val, "system-run-symbolic"), 0, 0, 1, 1)
        grid.attach(self._metric_card("MEMORY", self._mem_val, "media-flash-symbolic"), 1, 0, 1, 1)
        grid.attach(self._metric_card("DISK FREE", self._disk_val, "drive-harddisk-symbolic"), 2, 0, 1, 1)
        grid.attach(self._metric_card("UPTIME", self._uptime_val, "emblem-synchronizing-symbolic"), 3, 0, 1, 1)

        return grid

    def _metric_card(self, title: str, val_lbl: Gtk.Label, icon: str) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("metric-card")
        card.set_hexpand(True)

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        img = Gtk.Image.new_from_icon_name(icon)
        img.set_pixel_size(13)
        img.add_css_class("dim-label")
        lbl = Gtk.Label(label=title)
        lbl.add_css_class("metric-card-title")
        top_row.append(img)
        top_row.append(lbl)

        val_lbl.add_css_class("metric-card-value")
        val_lbl.set_halign(Gtk.Align.START)

        card.append(top_row)
        card.append(val_lbl)
        return card

    # ── Quick actions ────────────────────────────────────────────────

    def _build_quick_actions(self) -> Gtk.Widget:
        lbl = Gtk.Label(label="QUICK LINKS")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_top(16)
        lbl.set_margin_bottom(8)
        lbl.add_css_class("section-title")

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        actions = [
            ("Servers & Docker", "network-server-symbolic",
             lambda *_: navigate_workstation_section("servers")),
            ("Install Tools", "folder-download-symbolic",
             lambda *_: navigate_workstation_section("install")),
            ("Config & Dotfiles", "emblem-synchronizing-symbolic",
             lambda *_: navigate_workstation_section("config")),
            ("AI & Models", "preferences-desktop-accessibility-symbolic",
             lambda *_: navigate_workstation_section("ai")),
        ]
        for label, icon, handler in actions:
            btn = Gtk.Button()
            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            box.set_margin_top(7)
            box.set_margin_bottom(7)
            box.set_margin_start(12)
            box.set_margin_end(12)
            img = Gtk.Image.new_from_icon_name(icon)
            img.set_pixel_size(15)
            lbl_w = Gtk.Label(label=label)
            box.append(img)
            box.append(lbl_w)
            btn.set_child(box)
            btn.add_css_class("quick-link-btn")
            btn.set_hexpand(True)
            btn.connect("clicked", handler)
            row.append(btn)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(lbl)
        outer.append(row)
        return outer

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
        return True

    def _do_fetch(self) -> None:
        if self._fetch_running:
            return
        self._fetch_running = True
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self) -> None:
        """Runs in background thread — NO GTK calls here."""
        try:
            from core.setup.host_executor import HostExecutor
            from ui.widgets.workstation.servers_overview import (
                _host_cpu_pct_between_samples,
                _parse_mem_pct,
            )
            ex = HostExecutor()
            cpu = _host_cpu_pct_between_samples(ex)
            _, mem_str = _parse_mem_pct(ex)

            r = ex.run_sync(["df", "-h", "/"], timeout=5)
            disk_str = "—"
            if r.success and len(r.stdout.splitlines()) > 1:
                parts = r.stdout.splitlines()[1].split()
                if len(parts) > 3:
                    disk_str = f"{parts[3]} free"

            up = ex.run_sync(["uptime", "-p"], timeout=5)
            uptime_str = up.stdout.strip().removeprefix("up ") if up.success else "—"

            GLib.idle_add(self._apply_stats, cpu, mem_str, disk_str, uptime_str)
        except Exception:
            log.exception("Dashboard stats fetch failed")
        finally:
            self._fetch_running = False

    def _apply_stats(self, cpu: float, mem: str, disk: str, uptime: str) -> None:
        if self._cpu_val:
            self._cpu_val.set_label(f"{cpu:.1f}%")
        if self._mem_val:
            self._mem_val.set_label(mem)
        if self._disk_val:
            self._disk_val.set_label(disk)
        if self._uptime_val:
            self._uptime_val.set_label(uptime)
        if self._status_dot and self._status_lbl:
            if cpu > 85:
                self._status_dot.set_css_classes(["status-dot-warning"])
                self._status_lbl.set_label("HIGH LOAD")
            else:
                self._status_dot.set_css_classes(["status-dot-healthy"])
                self._status_lbl.set_label("HEALTHY")

    # ── Header action ─────────────────────────────────────────────────

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
        if hasattr(self, "_grid"):
            self._grid.add_widget_by_id(widget_id)
