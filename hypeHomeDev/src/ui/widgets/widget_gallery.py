"""HypeDevHome — Gallery dialog for choosing dashboard widgets."""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ui.widgets.empty_state import EmptyState  # noqa: E402
from ui.widgets.registry import registry  # noqa: E402

log = logging.getLogger(__name__)


class WidgetGalleryDialog(Adw.Window):
    """Dialog for browsing and adding widgets to the dashboard."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.set_title("Widget Gallery")
        self.set_default_size(700, 800)
        self.set_modal(True)

        self._selection_callback = None
        self._all_widgets: list[dict[str, Any]] = []
        self._filtered_widgets: list[dict[str, Any]] = []
        self._current_category: str = "All"
        self._search_text: str = ""

        # UI Setup
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header
        header = Adw.HeaderBar()
        content_box.append(header)

        # Search and filter bar
        search_filter_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        search_filter_box.set_margin_start(12)
        search_filter_box.set_margin_end(12)
        search_filter_box.set_margin_top(12)
        search_filter_box.set_margin_bottom(6)

        # Search bar
        self._search_bar = Gtk.SearchEntry()
        self._search_bar.set_placeholder_text("Search widgets by name or description…")
        self._search_bar.connect("search-changed", self._on_search_changed)
        search_filter_box.append(self._search_bar)

        # Category filter
        category_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        category_label = Gtk.Label(label="Category:")
        category_label.set_halign(Gtk.Align.START)
        category_box.append(category_label)

        self._category_dropdown = Gtk.DropDown.new_from_strings(["All"])
        self._category_dropdown.connect("notify::selected", self._on_category_changed)
        category_box.append(self._category_dropdown)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        category_box.append(spacer)

        search_filter_box.append(category_box)
        content_box.append(search_filter_box)

        # Main content: split view for preview
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)
        main_box.set_margin_bottom(12)
        main_box.set_vexpand(True)

        # Left panel: widget list
        left_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        left_panel.set_hexpand(False)
        left_panel.set_size_request(300, -1)

        # Widget list with empty state
        self._list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._list_container.set_vexpand(True)

        # Empty state
        self._empty_state = EmptyState(
            icon_name="view-grid-symbolic",
            title="No widgets found",
            description="Try changing your search or filter",
            button_label="Clear Filters",
            button_action=self._clear_filters,
        )
        self._empty_state.hide()
        self._list_container.append(self._empty_state)

        # Widget list
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.connect("row-selected", self._on_row_selected)
        self._list_box.connect("row-activated", self._on_row_activated)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._list_box)
        self._list_container.append(scrolled)

        left_panel.append(self._list_container)
        main_box.append(left_panel)

        # Right panel: preview
        right_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        right_panel.set_hexpand(True)

        # Preview header
        preview_header = Adw.HeaderBar()
        preview_header.set_title_widget(Gtk.Label(label="Preview"))
        preview_header.set_show_end_title_buttons(False)
        preview_header.set_show_start_title_buttons(False)
        right_panel.append(preview_header)

        # Preview container
        self._preview_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._preview_container.set_vexpand(True)
        self._preview_container.set_margin_start(12)
        self._preview_container.set_margin_end(12)
        self._preview_container.set_margin_bottom(12)

        # Preview placeholder
        self._preview_placeholder = EmptyState(
            icon_name="view-grid-symbolic",
            title="Select a widget to preview",
            description="Click on a widget in the list to see a preview",
            button_label=None,
        )
        self._preview_container.append(self._preview_placeholder)

        # Actual preview widget (initially hidden)
        self._preview_widget = None
        self._preview_scrolled = Gtk.ScrolledWindow()
        self._preview_scrolled.set_vexpand(True)
        self._preview_scrolled.set_min_content_height(300)
        self._preview_scrolled.hide()
        self._preview_container.append(self._preview_scrolled)

        right_panel.append(self._preview_container)

        # Add button (initially disabled)
        self._add_button = Gtk.Button.new_with_label("Add to Dashboard")
        self._add_button.set_icon_name("list-add-symbolic")
        self._add_button.add_css_class("suggested-action")
        self._add_button.set_tooltip_text(
            "Pick a widget in the list (not the category heading), then click here — or double-click the row"
        )
        self._add_button.set_sensitive(False)
        self._add_button.connect("clicked", self._on_add_clicked)
        self._add_button.set_margin_start(12)
        self._add_button.set_margin_end(12)
        self._add_button.set_margin_bottom(12)
        right_panel.append(self._add_button)

        main_box.append(right_panel)
        content_box.append(main_box)

        self.set_content(content_box)
        self._load_widget_list()

    def _load_widget_list(self) -> None:
        """Load all widgets from the registry and populate the list."""
        widget_ids = registry.list_widgets()
        categories = set()

        for widget_id in widget_ids:
            widget_class = registry.get_widget_class(widget_id)
            if not widget_class:
                continue

            # Get metadata from class if available
            title = getattr(widget_class, "widget_title", widget_id.replace("-", " ").title())
            icon = getattr(widget_class, "widget_icon", "view-grid-symbolic")
            category = getattr(widget_class, "widget_category", "Other")
            description = getattr(widget_class, "widget_description", "")

            categories.add(category)

            self._all_widgets.append(
                {
                    "id": widget_id,
                    "title": title,
                    "icon": icon,
                    "category": category,
                    "description": description,
                    "class": widget_class,
                }
            )

        # Update category dropdown
        category_list = ["All", *sorted(categories)]
        self._category_dropdown.set_model(Gtk.StringList.new(category_list))

        # Apply initial filter
        self._apply_filters()

    def _apply_filters(self) -> None:
        """Apply current search and category filters."""
        self._filtered_widgets = []

        for widget in self._all_widgets:
            # Category filter
            if self._current_category != "All" and widget["category"] != self._current_category:
                continue

            # Search filter
            if self._search_text:
                search_lower = self._search_text.lower()
                title_match = search_lower in widget["title"].lower()
                desc_match = search_lower in widget["description"].lower()
                id_match = search_lower in widget["id"].lower()
                if not (title_match or desc_match or id_match):
                    continue

            self._filtered_widgets.append(widget)

        self._update_widget_list()

    def _update_widget_list(self) -> None:
        """Update the widget list UI based on filtered widgets."""
        # Clear existing rows
        child = self._list_box.get_first_child()
        while child:
            self._list_box.remove(child)
            child = self._list_box.get_first_child()

        if not self._filtered_widgets:
            # Show empty state
            self._empty_state.show()
            self._list_box.hide()
            return

        # Hide empty state and show list
        self._empty_state.hide()
        self._list_box.show()

        # Group by category
        widgets_by_category: dict[str, list[dict[str, Any]]] = {}
        for widget in self._filtered_widgets:
            category = widget["category"]
            if category not in widgets_by_category:
                widgets_by_category[category] = []
            widgets_by_category[category].append(widget)

        # Create UI for each category
        for category, widgets in sorted(widgets_by_category.items()):
            # Add category header
            category_row = Adw.ActionRow()
            category_row.set_title(category)
            category_row.set_title_lines(1)
            category_row.add_css_class("heading")
            category_row.set_selectable(False)
            category_row.set_activatable(False)
            self._list_box.append(category_row)

            # Add widgets in this category
            for widget in sorted(widgets, key=lambda w: w["title"]):
                row = Adw.ActionRow()
                row.set_title(widget["title"])
                if widget["description"]:
                    row.set_subtitle(widget["description"])
                else:
                    row.set_subtitle(f"ID: {widget['id']}")
                row.set_icon_name(widget["icon"])

                # Use a custom property to store the widget data
                row.widget_data = widget  # type: ignore

                self._list_box.append(row)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        """Handle search text change."""
        self._search_text = entry.get_text().strip()
        self._apply_filters()

    def _on_category_changed(self, dropdown: Gtk.DropDown, _param: Any) -> None:
        """Handle category selection change."""
        selected = dropdown.get_selected()
        if selected == 0:
            self._current_category = "All"
        else:
            model = dropdown.get_model()
            if model and hasattr(model, "get_string"):
                self._current_category = model.get_string(selected)
            elif model:
                # Fallback for StringList models
                self._current_category = str(model.get_item(selected))
        self._apply_filters()

    def _clear_filters(self) -> None:
        """Clear all filters."""
        self._search_bar.set_text("")
        self._category_dropdown.set_selected(0)
        self._search_text = ""
        self._current_category = "All"
        self._apply_filters()

    def _on_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Handle widget selection in the list."""
        if not row:
            self._hide_widget_preview()
            self._add_button.set_sensitive(False)
            self._selected_widget_id = None
            return

        # Adw.ActionRow might be the row itself, or it might be a child
        widget_data = None
        if hasattr(row, "widget_data"):
            widget_data = row.widget_data  # type: ignore
        else:
            child = row.get_child()
            if child and hasattr(child, "widget_data"):
                widget_data = child.widget_data  # type: ignore

        if widget_data:
            self._show_widget_preview(widget_data)
            self._add_button.set_sensitive(True)
            self._selected_widget_id = widget_data["id"]
        else:
            self._hide_widget_preview()
            self._add_button.set_sensitive(False)
            self._selected_widget_id = None

    def _on_row_activated(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        """Double-click / keyboard activate: add widget if row holds widget_data."""
        widget_data = None
        if hasattr(row, "widget_data"):
            widget_data = row.widget_data  # type: ignore[attr-defined]
        else:
            child = row.get_child()
            if child and hasattr(child, "widget_data"):
                widget_data = child.widget_data  # type: ignore[attr-defined]
        if widget_data and self._selection_callback:
            self._selection_callback(widget_data["id"])
            self.close()

    def _show_widget_preview(self, widget_data: dict[str, Any]) -> None:
        """Show a preview of the selected widget."""
        # Hide placeholder
        self._preview_placeholder.hide()

        # Remove old preview widget
        if self._preview_widget:
            self._preview_scrolled.set_child(None)
            self._preview_widget = None

        try:
            # Create preview widget instance
            widget_class = widget_data["class"]
            preview_widget = widget_class()

            # Set a fixed size for preview
            preview_widget.set_size_request(400, 300)

            # Add to scrolled window
            self._preview_scrolled.set_child(preview_widget)
            self._preview_widget = preview_widget
            self._preview_scrolled.show()

            # Try to activate the widget (start its timers, etc.)
            if hasattr(preview_widget, "on_activate"):
                GLib.idle_add(preview_widget.on_activate)

        except Exception as e:
            log.error("Failed to create widget preview: %s", e)
            # Show error in preview
            error_label = Gtk.Label(label=f"Failed to create preview: {e!s}")
            error_label.add_css_class("error")
            error_label.set_wrap(True)
            self._preview_scrolled.set_child(error_label)
            self._preview_scrolled.show()

    def _hide_widget_preview(self) -> None:
        """Hide the widget preview and show placeholder."""
        # Show placeholder
        self._preview_placeholder.show()

        # Clean up preview widget
        if self._preview_widget:
            if hasattr(self._preview_widget, "on_deactivate"):
                self._preview_widget.on_deactivate()
            self._preview_scrolled.set_child(None)
            self._preview_widget = None
            self._preview_scrolled.hide()

    def _on_add_clicked(self, _button: Gtk.Button) -> None:
        """Handle add button click."""
        if hasattr(self, "_selected_widget_id") and self._selected_widget_id:
            if self._selection_callback:
                self._selection_callback(self._selected_widget_id)
            self.close()

    def set_selection_callback(self, callback: Any) -> None:
        """Set a function to be called when a widget is selected."""
        self._selection_callback = callback
