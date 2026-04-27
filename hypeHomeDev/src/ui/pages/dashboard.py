"""HypeDevHome - Dashboard page."""

from __future__ import annotations

import logging

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Gtk  # noqa: E402

# AppState removed as it is now handled by DashboardGrid
from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.dashboard_grid import DashboardGrid  # noqa: E402
from ui.widgets.widget_gallery import WidgetGalleryDialog  # noqa: E402

log = logging.getLogger(__name__)


class DashboardPage(BasePage):
    """Widget grid: real-time system and GitHub cards (main rail: Widgets)."""

    page_title = "Widgets"
    page_icon = "view-grid-symbolic"

    def build_content(self) -> None:
        self._grid = DashboardGrid()
        self.append(self._grid)

    def on_shown(self) -> None:
        """Called each time the page is displayed."""
        super().on_shown()
        # Do not call load_widgets() here: it clears the FlowBox and rebuilds from
        # saved layout. Wrong legacy widget ids used to drop GitHub widgets on every visit.

    def get_header_actions(self) -> list[Gtk.Widget]:
        """Add an 'Add Widget' button to the header bar."""
        add_btn = Gtk.Button.new_from_icon_name("list-add-symbolic")
        add_btn.set_tooltip_text("Add Widget")
        add_btn.connect("clicked", self._on_add_widget_clicked)
        return [add_btn]

    def _on_add_widget_clicked(self, _btn: Gtk.Button) -> None:
        """Show the widget gallery dialog."""
        win = self.get_root()
        gallery = WidgetGalleryDialog(transient_for=win)
        gallery.set_selection_callback(self._on_widget_selected)
        gallery.present()

    def _on_widget_selected(self, widget_id: str) -> None:
        """Handle widget selection from gallery."""
        log.info("Selected widget to add: %s", widget_id)
        if hasattr(self, "_grid"):
            self._grid.add_widget_by_id(widget_id)
