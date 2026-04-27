"""HypeDevHome — Welcome dashboard (default entry).

Outcome wizards, system health, servers/containers overview, and contextual
terminal reference (session + Bash) — see new_plan.md Phase 2.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.workstation.bash_cheatsheet import BashCheatsheetPage  # noqa: E402
from ui.widgets.workstation.nav_helper import (  # noqa: E402
    navigate_main_window,
    navigate_workstation_section,
)
from ui.widgets.workstation.panels import build_session_keybindings_page  # noqa: E402
from ui.widgets.workstation.system_dashboard import WorkstationSystemDashboardPanel  # noqa: E402

log = logging.getLogger(__name__)


def _expander_block(title: str, body: Gtk.Widget) -> Gtk.Expander:
    """Standard expander so sections read as collapsible panels, not plain text."""
    exp = Gtk.Expander(label=title)
    exp.set_child(body)
    exp.set_expanded(False)
    exp.set_margin_start(18)
    exp.set_margin_end(18)
    exp.set_margin_top(4)
    exp.set_margin_bottom(8)
    return exp


def _welcome_nav_button(label: str, icon_name: str, handler) -> Gtk.Button:
    btn = Gtk.Button()
    btn.set_child(Adw.ButtonContent(icon_name=icon_name, label=label))
    btn.set_hexpand(True)
    btn.set_halign(Gtk.Align.FILL)
    btn.connect("clicked", handler)
    btn.set_tooltip_text(label)
    return btn


class WelcomeDashboardPage(BasePage):
    """Welcome: wizards, health cards, live overview, and collapsible terminal reference."""

    page_title = "Welcome"
    page_icon = "user-home-symbolic"

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

        dash = WorkstationSystemDashboardPanel()
        outer.append(dash)

        ql_hdr = Gtk.Label(label="Quick links")
        ql_hdr.set_halign(Gtk.Align.START)
        ql_hdr.set_margin_start(24)
        ql_hdr.set_margin_end(24)
        ql_hdr.set_margin_top(6)
        ql_hdr.add_css_class("heading")
        outer.append(ql_hdr)

        ql_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ql_col.set_margin_start(20)
        ql_col.set_margin_end(20)
        ql_col.set_margin_bottom(10)

        ql_col.append(
            _welcome_nav_button(
                "System Monitor",
                "utilities-system-monitor-symbolic",
                lambda *_: navigate_main_window("system"),
            ),
        )
        ql_col.append(
            _welcome_nav_button(
                "Tools → Servers",
                "network-server-symbolic",
                lambda *_: navigate_workstation_section("servers"),
            ),
        )
        ql_col.append(
            _welcome_nav_button(
                "Docker Docs",
                "globe-symbolic",
                lambda *_: navigate_workstation_section("servers:docs"),
            ),
        )
        ql_col.append(
            _welcome_nav_button(
                "Tools → Install",
                "folder-download-symbolic",
                lambda *_: navigate_workstation_section("install"),
            ),
        )
        ql_col.append(
            _welcome_nav_button(
                "Config → CLI",
                "emblem-synchronizing-symbolic",
                lambda *_: navigate_workstation_section("config:cli"),
            ),
        )
        ql_col.append(
            _welcome_nav_button(
                "Widgets",
                "view-app-grid-symbolic",
                lambda *_: navigate_main_window("dashboard"),
            ),
        )
        outer.append(ql_col)

        tips_hdr = Gtk.Label(label="Terminal & desktop reference")
        tips_hdr.set_halign(Gtk.Align.START)
        tips_hdr.set_margin_start(24)
        tips_hdr.set_margin_end(24)
        tips_hdr.set_margin_top(8)
        tips_hdr.add_css_class("heading")
        outer.append(tips_hdr)

        tips_sub = Gtk.Label(
            label="Moved from the old Learn tab — expand when you need copy-paste commands or session info.",
        )
        tips_sub.set_halign(Gtk.Align.START)
        tips_sub.set_margin_start(24)
        tips_sub.set_margin_end(24)
        tips_sub.set_wrap(True)
        tips_sub.add_css_class("dim-label")
        outer.append(tips_sub)

        sess_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            height_request=280,
        )
        sess_scroll.set_child(build_session_keybindings_page())
        outer.append(_expander_block("Session & desktop keys", sess_scroll))

        bash_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            height_request=420,
        )
        bash_scroll.set_child(BashCheatsheetPage())
        outer.append(_expander_block("Bash scripting tips", bash_scroll))

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(8)
        sep.set_margin_bottom(8)
        outer.append(sep)

        mon_hdr = Gtk.Label(label="Host & Docker chart")
        mon_hdr.set_halign(Gtk.Align.START)
        mon_hdr.set_margin_start(24)
        mon_hdr.set_margin_end(24)
        mon_hdr.add_css_class("heading")
        outer.append(mon_hdr)

        mon_sub = Gtk.Label(
            label=(
                "That live table is only on System Monitor and Tools → Servers → Overview "
                "so it stays scrollable and is not pasted twice here."
            ),
        )
        mon_sub.set_halign(Gtk.Align.START)
        mon_sub.set_margin_start(24)
        mon_sub.set_margin_end(24)
        mon_sub.set_margin_bottom(12)
        mon_sub.set_wrap(True)
        mon_sub.add_css_class("dim-label")
        outer.append(mon_sub)

        scroll.set_child(outer)
        self.append(scroll)

    def on_shown(self) -> None:
        super().on_shown()
        log.debug("Welcome dashboard shown")

    def on_hidden(self) -> None:
        super().on_hidden()

    def get_header_actions(self) -> list[Gtk.Widget]:
        return []
