"""HypeDevHome — Base class for dashboard widgets."""

from __future__ import annotations

import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from ui.widgets.card import Card  # noqa: E402

log = logging.getLogger(__name__)


class DashboardWidget(Card):
    """Base class for all dashboard widgets.

    Inherits from Card to provide a standard look and feel.
    Widgets should override ``build_ui()`` to add their specific content.
    """

    def __init__(
        self,
        widget_id: str,
        title: str,
        icon_name: str | None = None,
        refresh_interval: float = 2.0,
        **kwargs: Any,
    ) -> None:
        """Initialize the dashboard widget.

        Args:
            widget_id: Unique identifier for this widget type.
            title: Human-readable title.
            icon_name: Optional icon name for the header.
            refresh_interval: Time in seconds between updates.
        """
        super().__init__(**kwargs)
        self.widget_id = widget_id
        self.title = title
        self.icon_name = icon_name
        self._refresh_interval = refresh_interval
        self._refresh_timer_id = 0
        self._width_span = kwargs.get("width_span", 1)
        self._height_span = kwargs.get("height_span", 1)
        self._disposed = False

        # UI Setup
        self._setup_widget_header()
        self._setup_actions()
        self._apply_size_request()
        self.build_ui()

    def _setup_widget_header(self) -> None:
        """Create a standard header with centered icon+title and end menu."""
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        header_row.add_css_class("widget-header")
        header_row.set_margin_bottom(8)

        left_spacer = Gtk.Box()
        left_spacer.set_hexpand(True)

        # Icon + title as one unit, centered in the header row (between spacers).
        center_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        center_row.set_hexpand(False)
        center_row.set_halign(Gtk.Align.CENTER)
        center_row.set_valign(Gtk.Align.CENTER)

        if self.icon_name:
            icon = Gtk.Image.new_from_icon_name(self.icon_name)
            icon.set_pixel_size(22)
            icon.set_valign(Gtk.Align.CENTER)
            center_row.append(icon)

        title_label = Gtk.Label(label=self.title)
        title_label.add_css_class("heading")
        title_label.set_halign(Gtk.Align.CENTER)
        title_label.set_valign(Gtk.Align.CENTER)
        title_label.set_justify(Gtk.Justification.CENTER)
        center_row.append(title_label)

        right_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        right_area.set_hexpand(True)
        right_area.set_halign(Gtk.Align.END)

        # Widget menu
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("view-more-symbolic")
        menu_button.set_has_frame(False)
        menu_button.set_tooltip_text(
            "Resize, configure, or remove this widget (drag the header to reorder)"
        )

        # Create menu model
        menu = Gio.Menu()

        # Resize submenu (Agent A)
        # Action group name is "widget"; actions are configure/remove/resize_* (not widget.<id>.remove).
        resize_menu = Gio.Menu()
        resize_menu.append("Small (1x1)", "widget.resize_small")
        resize_menu.append("Wide (2x1)", "widget.resize_wide")
        resize_menu.append("Large (2x2)", "widget.resize_large")
        menu.append_submenu("Resize", resize_menu)

        menu.append("Configure…", "widget.configure")
        menu.append("Remove", "widget.remove")
        menu_button.set_menu_model(menu)

        right_area.append(menu_button)
        header_row.append(left_spacer)
        header_row.append(center_row)
        header_row.append(right_area)
        self.append(header_row)

        # DRAG AND DROP SETUP (Agent A)
        self._setup_drag_source(header_row)

    def _setup_drag_source(self, target: Gtk.Widget) -> None:
        """Set up DragSource on the given target widget."""
        drag_source = Gtk.DragSource.new()
        drag_source.set_actions(gi.repository.Gdk.DragAction.MOVE)

        drag_source.connect("prepare", self._on_drag_prepare)
        drag_source.connect("drag-begin", self._on_drag_begin)
        drag_source.connect("drag-cancel", self._on_drag_cancel)

        # Attach to target (header)
        target.add_controller(drag_source)
        log.debug("DragSource attached to widget header: %s", self.widget_id)

    def _on_drag_prepare(
        self, source: Gtk.DragSource, _x: float, _y: float
    ) -> gi.repository.Gdk.ContentProvider | None:
        """Called when drag starts. Provides the widget identifier."""
        # We pass the widget ID and current memory address as a simple identifier
        value = GLib.Variant("s", f"{self.widget_id}:{id(self)}")
        content = gi.repository.Gdk.ContentProvider.new_for_value(value)
        return content

    def _on_drag_begin(self, source: Gtk.DragSource, _drag: gi.repository.Gdk.Drag) -> None:
        """Set the drag icon snapshot."""
        # Create a snapshot of the widget to use as icon
        paintable = Gtk.WidgetPaintable.new(self)
        source.set_icon(paintable, 0, 0)
        self.add_css_class("dragging")

    def _on_drag_cancel(
        self,
        _source: Gtk.DragSource,
        _drag: gi.repository.Gdk.Drag,
        _reason: gi.repository.Gdk.DragCancelReason,
    ) -> bool:
        """Clear dimming when drag is cancelled (drop path clears in DashboardGrid).

        GTK 4.16+ passes ``reason`` and expects a bool: return True to skip the default
        failed-drag animation (we only reset styling).
        """
        self.remove_css_class("dragging")
        return False

    def _setup_actions(self) -> None:
        """Set up GActions for the widget."""
        group = Gio.SimpleActionGroup.new()

        # Configure action
        configure_action = Gio.SimpleAction.new("configure", None)
        configure_action.connect("activate", self._on_configure_action)
        group.add_action(configure_action)

        # Remove action
        remove_action = Gio.SimpleAction.new("remove", None)
        remove_action.connect("activate", self._on_remove_action)
        group.add_action(remove_action)

        # Resize actions (Agent A)
        resize_small_action = Gio.SimpleAction.new("resize_small", None)
        resize_small_action.connect("activate", lambda *_: self._resize(1, 1))
        group.add_action(resize_small_action)

        resize_wide_action = Gio.SimpleAction.new("resize_wide", None)
        resize_wide_action.connect("activate", lambda *_: self._resize(2, 1))
        group.add_action(resize_wide_action)

        resize_large_action = Gio.SimpleAction.new("resize_large", None)
        resize_large_action.connect("activate", lambda *_: self._resize(2, 2))
        group.add_action(resize_large_action)

        self.insert_action_group("widget", group)

    def _on_configure_action(self, _action: Gio.SimpleAction, _param: None) -> None:
        """Handle the configure action."""
        log.debug("Configure requested for %s", self.widget_id)
        self.show_settings_dialog()

    def show_settings_dialog(self) -> None:
        """Show the settings dialog for this widget.

        Override this method in subclasses to provide custom settings.

        The base implementation provides common settings like refresh interval.
        """

        dialog = Adw.PreferencesDialog(
            title=f"{self.title} Settings",
        )
        # Settings dialog in Libadwaita 1.4+ is presented via present(parent)
        root = self.get_root()
        parent = cast(Gtk.Window, root) if isinstance(root, Gtk.Window) else None

        # General page
        page = Adw.PreferencesPage()
        dialog.add(page)

        # General settings group
        group = Adw.PreferencesGroup(
            title="General Settings", description="Configure widget behavior"
        )
        page.add(group)

        # Refresh interval
        row = Adw.SpinRow(
            title="Refresh interval",
            subtitle="Seconds between updates (0 to disable)",
            adjustment=Gtk.Adjustment(
                value=self._refresh_interval,
                lower=0.0,
                upper=60.0,
                step_increment=0.5,
                page_increment=5.0,
            ),
        )
        row.connect("changed", self._on_refresh_interval_changed)
        group.add(row)

        dialog.present(parent)

    def _on_refresh_interval_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle refresh interval change."""
        new_interval = spin_row.get_value()
        if new_interval != self._refresh_interval:
            self._refresh_interval = new_interval
            log.debug(
                "Refresh interval changed to %f seconds for %s", new_interval, self.widget_id
            )

            # Restart timer if widget is active
            if self._refresh_timer_id > 0:
                self._stop_refresh_timer()
                if new_interval > 0:
                    self._start_refresh_timer()

    def _on_remove_action(self, _action: Gio.SimpleAction, _param: None) -> None:
        """Handle the remove action."""
        log.debug("Remove requested for %s", self.widget_id)
        from ui.widgets.dashboard_grid import DashboardGrid

        parent = self.get_parent()
        while parent:
            if isinstance(parent, DashboardGrid):
                parent.remove_widget(self)
                return
            parent = parent.get_parent()

    def build_ui(self) -> None:
        """Override this to add the widget's specific content.

        Use ``self.append(widget)`` to add children after the header.
        """
        pass

    def on_activate(self) -> None:
        """Called when the widget is added to the dashboard or app starts.

        Starts the refresh timer.
        """
        if self._refresh_interval > 0:
            self._start_refresh_timer()
        log.debug("Widget activated: %s", self.widget_id)

    def on_deactivate(self) -> None:
        """Called when the widget is removed or app closes.

        Stops the refresh timer and cleans up resources.
        """
        self._stop_refresh_timer()
        log.debug("Widget deactivated: %s", self.widget_id)

    def refresh(self) -> bool:
        """Override this to update the widget's data.

        Returns:
            True to continue calling this method periodically.
        """
        return True

    def _start_refresh_timer(self) -> None:
        """Start a periodic GLib timer for refreshing the widget."""
        self._stop_refresh_timer()
        interval_ms = int(self._refresh_interval * 1000)
        self._refresh_timer_id = GLib.timeout_add(interval_ms, self.refresh)

    def _stop_refresh_timer(self) -> None:
        """Stop the periodic refresh timer."""
        if self._refresh_timer_id > 0:
            GLib.source_remove(self._refresh_timer_id)
            self._refresh_timer_id = 0

    def get_config(self) -> dict[str, Any]:
        """Return the current widget configuration for persistence."""
        return {
            "id": self.widget_id,
            "refresh_interval": self._refresh_interval,
            "width_span": self._width_span,
            "height_span": self._height_span,
        }

    def dispose(self) -> None:
        """Clean up widget resources and stop active refresh timers."""
        if self._disposed:
            return

        self._disposed = True
        self.on_deactivate()

        try:
            self.remove_action_group("widget")  # type: ignore[attr-defined]
        except Exception:
            log.debug("Failed to remove widget action group cleanly", exc_info=True)

    def __del__(self) -> None:
        try:
            self.dispose()
        except Exception:
            log.debug("Error during widget cleanup", exc_info=True)

    def _apply_size_request(self) -> None:
        """Apply size based on spans. To be refined by the grid."""
        # Baseline: 1 span unit is ~280px in our current grid layout (1200px max)
        base_w = 280
        base_h = 240
        self.set_size_request(
            base_w * self._width_span + (self._width_span - 1) * 12,
            base_h * self._height_span + (self._height_span - 1) * 12,
        )

    def _resize(self, w: int, h: int) -> None:
        """Update spans and request layout update."""
        log.info("Resizing widget %s to %dx%d", self.widget_id, w, h)
        self._width_span = w
        self._height_span = h
        self._apply_size_request()

        from ui.widgets.dashboard_grid import DashboardGrid

        p: Gtk.Widget | None = self.get_parent()
        while p:
            if isinstance(p, DashboardGrid):
                p._update_state_from_layout()
                return
            p = p.get_parent()
