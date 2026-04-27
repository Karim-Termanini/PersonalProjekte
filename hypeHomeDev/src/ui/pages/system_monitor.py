"""HypeDevHome — Dedicated system monitor page (new_plan.md Task 1.3).

Host load, CPU/memory sparklines, containers/LAN table — reuses
``WorkstationServersOverviewPanel`` (same data as Tools → Servers → Overview).
"""

from __future__ import annotations

import logging
import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.workstation.linux_filesystem_page import LinuxFilesystemPage  # noqa: E402
from ui.widgets.workstation.servers_overview import WorkstationServersOverviewPanel  # noqa: E402

log = logging.getLogger(__name__)


class SystemMonitorPage(BasePage):
    """Full-width live monitor (local host + containers + neighbors)."""

    page_title = "System Monitor"
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

        title = Gtk.Label(label="Live monitoring")
        title.set_halign(Gtk.Align.START)
        title.set_margin_start(18)
        title.set_margin_end(18)
        title.set_margin_top(12)
        title.add_css_class("title-2")
        outer.append(title)

        sub = Gtk.Label(
            label=(
                "Host load, Docker rows, and LAN neighbors — one scrollable page "
                "(Ctrl+2). Detailed charts also live under Tools → Servers → Overview."
            ),
        )
        sub.set_halign(Gtk.Align.START)
        sub.set_margin_start(18)
        sub.set_margin_end(18)
        sub.set_margin_bottom(8)
        sub.set_wrap(True)
        sub.add_css_class("dim-label")
        outer.append(sub)

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

        fhs_hdr = Gtk.Label(label="Linux filesystem (FHS)")
        fhs_hdr.set_halign(Gtk.Align.START)
        fhs_hdr.set_margin_start(18)
        fhs_hdr.set_margin_end(18)
        fhs_hdr.set_margin_top(16)
        fhs_hdr.add_css_class("heading")
        outer.append(fhs_hdr)

        fhs_sub = Gtk.Label(
            label="Expand for the interactive directory tree (formerly under Learn).",
        )
        fhs_sub.set_halign(Gtk.Align.START)
        fhs_sub.set_margin_start(18)
        fhs_sub.set_margin_end(18)
        fhs_sub.set_wrap(True)
        fhs_sub.add_css_class("dim-label")
        outer.append(fhs_sub)

        fhs_btn = Gtk.ToggleButton(label="Show filesystem tree")
        fhs_btn.set_halign(Gtk.Align.START)
        fhs_btn.set_margin_start(18)
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
        log.debug("System monitor page shown")

    def get_header_actions(self) -> list[Gtk.Widget]:
        return []
