"""Tools → Home: navigation hub without duplicating Welcome wizards."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from ui.widgets.workstation.nav_helper import (  # noqa: E402
    navigate_main_window,
    navigate_workstation_section,
)


def _hub_nav_button(label: str, icon_name: str, handler) -> Gtk.Button:
    btn = Gtk.Button()
    btn.set_child(Adw.ButtonContent(icon_name=icon_name, label=label))
    btn.set_hexpand(True)
    btn.set_halign(Gtk.Align.FILL)
    btn.connect("clicked", handler)
    btn.set_tooltip_text(label)
    return btn


class WorkstationHubHomePanel(Gtk.Box):
    """Short hub: points to Welcome, System Monitor, and Servers tabs."""

    def __init__(self, **kw) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, **kw)
        self.set_margin_start(24)
        self.set_margin_end(24)
        self.set_margin_top(20)
        self.set_margin_bottom(24)

        title = Gtk.Label(label="Where things live")
        title.add_css_class("title-2")
        title.set_halign(Gtk.Align.START)
        self.append(title)

        intro = Gtk.Label(
            label=(
                "Wizards and the health strip stay on Welcome. "
                "The large host and Docker chart is on System Monitor and on Tools → Servers → Overview."
            ),
        )
        intro.set_wrap(True)
        intro.set_halign(Gtk.Align.START)
        intro.set_xalign(0.0)
        intro.add_css_class("dim-label")
        self.append(intro)

        links = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        links.set_margin_top(8)
        links.append(
            _hub_nav_button(
                "Welcome — wizards & health",
                "user-home-symbolic",
                lambda *_: navigate_main_window("welcome"),
            ),
        )
        links.append(
            _hub_nav_button(
                "System Monitor",
                "utilities-system-monitor-symbolic",
                lambda *_: navigate_main_window("system"),
            ),
        )
        links.append(
            _hub_nav_button(
                "Servers — Overview",
                "network-server-symbolic",
                lambda *_: navigate_workstation_section("servers:overview"),
            ),
        )
        links.append(
            _hub_nav_button(
                "Servers — Docker Docs",
                "globe-symbolic",
                lambda *_: navigate_workstation_section("servers:docs"),
            ),
        )
        self.append(links)

    def reset_subsections(self) -> None:
        """WorkstationPage resets subsections on hide; nothing to reset here."""
        pass
