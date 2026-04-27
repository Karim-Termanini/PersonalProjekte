"""HypeDevHome — Responsive grid for dashboard widgets."""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402
from ui.widgets.registry import registry  # noqa: E402

log = logging.getLogger(__name__)

# Old GitHub widgets saved id from class name (githubassignedwidget); registry uses github_assigned.
_LEGACY_WIDGET_IDS: dict[str, str] = {
    "githubassignedwidget": "github_assigned",
    "githubissueswidget": "github_issues",
    "githubprswidget": "github_prs",
    "githubreviewswidget": "github_reviews",
    "githubmentionswidget": "github_mentions",
    "githubreposwidget": "github_repos",
}


class DashboardGrid(Gtk.Box):
    """A responsive grid that manages dashboard widgets.

    Uses Gtk.FlowBox to allow widgets to reflow based on available width.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._flowbox = Gtk.FlowBox()
        self._flowbox.set_valign(Gtk.Align.START)
        self._flowbox.set_max_children_per_line(4)
        self._flowbox.set_min_children_per_line(1)
        self._flowbox.set_row_spacing(12)
        self._flowbox.set_column_spacing(12)
        self._flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flowbox.set_homogeneous(False)  # Allow widgets to have different widths

        # Allow reordering if needed in the future
        # self._flowbox.set_sort_func(...)

        # Wrap in Adw.Clamp for pleasant max-width on large screens
        clamp = Adw.Clamp()
        clamp.set_maximum_size(1200)
        clamp.set_tightening_threshold(800)
        clamp.set_child(self._flowbox)

        # Scrolling
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        try:
            scrolled.set_overlay_scrolling(False)
        except (AttributeError, TypeError):
            pass
        scrolled.set_child(clamp)

        self.append(scrolled)

        # Initial widget loading
        self.load_widgets()

        # DRAG AND DROP SETUP (Agent A)
        self._setup_drop_target()

    def _setup_drop_target(self) -> None:
        """Set up DropTarget on the FlowBox to handle reordering."""
        # Accept the string variant we created in DashboardWidget
        drop_target = Gtk.DropTarget.new(GLib.Variant, gi.repository.Gdk.DragAction.MOVE)
        drop_target.set_gtypes([GLib.Variant])
        drop_target.connect("drop", self._on_widget_dropped)
        self._flowbox.add_controller(drop_target)
        log.debug("DropTarget attached to DashboardGrid FlowBox")

    def _on_widget_dropped(
        self, _target: Gtk.DropTarget, value: GLib.Variant, x: float, y: float
    ) -> bool:
        """Handle a widget being dropped onto the grid."""
        try:
            # Parse identifier: "id:mem_address"
            info = value.get_string()
            source_id, source_addr = info.split(":")
            source_addr_int = int(source_addr)
            log.debug("Widget dropped: %s (x=%f, y=%f)", source_id, x, y)

            # Find the source widget by memory address
            # (In a real app, you might use a more robust ID system)
            source_widget: Gtk.Widget | None = None
            child = self._flowbox.get_first_child()
            while child:
                if isinstance(child, Gtk.FlowBoxChild):
                    inner = child.get_child()
                    if inner and id(inner) == source_addr_int:
                        source_widget = child
                        break
                child = child.get_next_sibling()

            if not source_widget:
                log.warning("Could not find source widget for drop")
                return False

            # Find target position
            target_child = self._flowbox.get_child_at_pos(int(x), int(y))
            if target_child:
                target_index = target_child.get_index()
                # Reorder
                log.info("Reordering widget to index %d", target_index)
                self._flowbox.remove(source_widget)
                self._flowbox.insert(source_widget, target_index)
            else:
                # Dropped at the end?
                log.info("Appended widget to the end of the grid")
                self._flowbox.remove(source_widget)
                self._flowbox.append(source_widget)

            # Remove dragging style from the dashboard widget (class is on inner, not FlowBoxChild)
            inner = source_widget.get_first_child()
            if inner is not None and inner.has_css_class("dragging"):
                inner.remove_css_class("dragging")

            self._update_state_from_layout()
            return True
        except Exception as e:
            log.error("Error during widget drop: %s", e)
            return False

    def load_widgets(self) -> None:
        """Clear the grid and load widgets from the current layout."""
        # Clear existing
        while True:
            child = self._flowbox.get_first_child()
            if not child:
                break
            self._flowbox.remove(child)

        # Load from AppState/Config
        state = AppState.get()
        layout = state.dashboard_layout

        if not layout:
            log.info("Dashboard layout is empty")
            return

        for widget_config in layout:
            widget_id = widget_config.get("id")
            if not widget_id:
                continue

            self.add_widget_by_id(widget_id, widget_config)

    def add_widget_by_id(self, widget_id: str, config: dict[str, Any] | None = None) -> bool:
        """Instantiate and add a widget to the grid.

        Args:
            widget_id: The ID of the widget type to add.
            config: Optional configuration for the widget instance.

        Returns:
            True if added successfully, False otherwise.
        """
        widget_id = _LEGACY_WIDGET_IDS.get(widget_id, widget_id)

        widget_class = registry.get_widget_class(widget_id)
        if not widget_class:
            log.warning("Widget type '%s' not found in registry", widget_id)
            return False

        try:
            # Subclasses pass widget_id in super(); passing it again + **config breaks with
            # TypeError: multiple values for keyword argument 'widget_id'. Saved layout uses "id".
            cfg = dict(config or {})
            cfg.pop("id", None)
            cfg.pop("widget_id", None)
            # Saved layout includes refresh_interval; subclasses also pass it to super() → duplicate kwarg.
            cfg.pop("refresh_interval", None)

            log.debug("Found widget class for '%s': %s", widget_id, widget_class.__name__)
            widget = widget_class(**cfg)

            # FlowBox appends the widget; FlowBoxChild is created automatically.
            # Do not hexpand: otherwise a single column fills the full line width and
            # resize (set_size_request) has no visible effect.
            self._flowbox.append(widget)

            widget.on_activate()

            log.info("Successfully added widget to dashboard: %s", widget_id)
            self._update_state_from_layout()
            return True
        except Exception as e:
            log.error("Failed to instantiate widget '%s': %s", widget_id, e, exc_info=True)
            return False

    def remove_widget(self, widget: Gtk.Widget) -> None:
        """Remove a widget from the grid and save the layout."""
        # Note: If widget is wrapped in FlowBoxChild, we need to find that
        parent = widget.get_parent()
        if isinstance(parent, Gtk.FlowBoxChild):
            self._flowbox.remove(parent)
        else:
            self._flowbox.remove(widget)

        if hasattr(widget, "on_deactivate"):
            widget.on_deactivate()

        log.info("Removed widget from dashboard")
        self._update_state_from_layout()

    def _update_state_from_layout(self) -> None:
        """Scan the grid and update AppState with the current layout."""
        new_layout = []
        child = self._flowbox.get_first_child()
        while child:
            # The widget is inside the FlowBoxChild
            if isinstance(child, Gtk.FlowBoxChild):
                widget = child.get_child()
                if widget and hasattr(widget, "get_config"):
                    new_layout.append(widget.get_config())
            child = child.get_next_sibling()

        state = AppState.get()
        state.dashboard_layout = new_layout
        if state.config:
            state.config.set("dashboard_layout", new_layout)
            state.config.save()
            log.debug("Dashboard layout saved to config")
