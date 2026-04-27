"""HypeDevHome — Monitor page.

Live system metrics only:
- Host load, CPU/memory, containers/LAN table
- Linux Filesystem (FHS) interactive tree
No duplicate content from Tools → Servers.
"""

from __future__ import annotations

import logging
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.workstation.linux_filesystem_page import LinuxFilesystemPage  # noqa: E402
from ui.widgets.workstation.servers_overview import WorkstationServersOverviewPanel  # noqa: E402

log = logging.getLogger(__name__)


class SystemMonitorPage(BasePage):
    """Full-width live monitor: local host + containers + filesystem reference."""

    page_title = "Monitor"
    page_icon = "utilities-system-monitor-symbolic"

    def build_content(self) -> None:
        self.set_hexpand(True)
        self.set_vexpand(True)

        scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hexpand=True,
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        try:
            scroll.set_overlay_scrolling(False)
        except (AttributeError, TypeError):
            pass

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_valign(Gtk.Align.START)

        # ── Live system overview ─────────────────────────────────
        monitor_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.NONE,
            vexpand=False,
            hexpand=True,
        )
        overview = WorkstationServersOverviewPanel(
            parent_stack=monitor_stack,
            shrink_for_embedding=True,
        )
        monitor_stack.add_named(overview, "overview")
        monitor_stack.set_visible_child_name("overview")
        outer.append(monitor_stack)

        # ── Linux Filesystem (FHS) reference ─────────────────────
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(16)
        sep.set_margin_bottom(4)
        outer.append(sep)

        fhs_hdr = Gtk.Label(label="LINUX FILESYSTEM (FHS)")
        fhs_hdr.set_halign(Gtk.Align.START)
        fhs_hdr.set_margin_start(18)
        fhs_hdr.set_margin_end(18)
        fhs_hdr.set_margin_top(8)
        fhs_hdr.set_margin_bottom(6)
        fhs_hdr.add_css_class("section-title")
        outer.append(fhs_hdr)

        fhs_btn = Gtk.ToggleButton(label="Show filesystem tree")
        fhs_btn.set_halign(Gtk.Align.START)
        fhs_btn.set_margin_start(18)
        fhs_btn.set_margin_bottom(8)
        fhs_rev = Gtk.Revealer(
            transition_type=Gtk.RevealerTransitionType.CROSSFADE,
            reveal_child=False,
        )
        fhs_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            height_request=480,
        )
        fhs_scroll.set_child(LinuxFilesystemPage())
        fhs_rev.set_child(fhs_scroll)
        fhs_btn.connect("toggled", lambda b: fhs_rev.set_reveal_child(b.get_active()))
        outer.append(fhs_btn)
        outer.append(fhs_rev)

        scroll.set_child(outer)
        self.append(scroll)

    def on_shown(self) -> None:
        super().on_shown()
        log.debug("Monitor page shown")

    def get_header_actions(self) -> list[Gtk.Widget]:
        return []
