"""HypeDevHome — Widget configuration dialog.

Generic dialog for configuring individual widget parameters such as
refresh interval, visibility toggles, and widget-specific options.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402


class WidgetConfigDialog(Adw.Window):
    """Modal window for configuring a single widget's options.

    Parameters
    ----------
    widget_id : str
        Identifier of the widget being configured.
    config : dict
        Current configuration values.
    on_save : callable
        Called with the updated config dict when the user saves.
    parent : Gtk.Window | None
        Parent window for modality.
    """

    def __init__(
        self,
        widget_id: str,
        config: dict[str, Any],
        on_save: Callable[[dict[str, Any]], None],
        parent: Gtk.Window | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._widget_id = widget_id
        self._config = dict(config)
        self._on_save = on_save
        if parent:
            self.set_transient_for(parent)

        self.set_title(f"Configure: {widget_id}")
        self.set_default_size(450, 400)
        self.set_child(self._build_content())

    def _build_content(self) -> Gtk.Widget:
        toolbar = Adw.ToolbarView()

        # Header bar
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", lambda *_: self._save())
        header.pack_end(save_btn)

        # Content
        clamp = Adw.Clamp()
        clamp.set_maximum_size(500)
        toolbar.set_content(clamp)

        page = Adw.PreferencesPage()
        clamp.set_child(page)

        group = Adw.PreferencesGroup(title=self._widget_id.replace("_", " ").title())
        page.add(group)

        # Refresh interval (common)
        interval_row = Adw.SpinRow(
            title="Refresh interval",
            subtitle="Seconds between data updates",
            adjustment=Gtk.Adjustment(
                value=self._config.get("refresh_interval", 2),
                lower=0.5,
                upper=30,
                step_increment=0.5,
                page_increment=5,
            ),
        )
        interval_row.set_numeric(True)
        interval_row.connect("notify::value", self._set_config("refresh_interval"))
        group.add(interval_row)

        # Widget-specific rows
        self._add_widget_rows(group)

        return toolbar

    def _add_widget_rows(self, group: Adw.PreferencesGroup) -> None:
        wid = self._widget_id.lower()

        if wid in ("memory", "memory_widget"):
            self._add_toggle(group, "Show swap", "show_swap", True)

        elif wid in ("network", "network_widget"):
            self._add_toggle(group, "Show peak speeds", "show_peak", True)
            self._add_toggle(group, "Show total transferred", "show_totals", True)

        elif wid in ("cpu", "cpu_widget"):
            self._add_toggle(group, "Show temperature", "show_temperature", True)
            self._add_toggle(group, "Show per-core", "show_per_core", True)

    def _add_toggle(
        self,
        group: Adw.PreferencesGroup,
        title: str,
        key: str,
        default: bool,
    ) -> None:
        row = Adw.SwitchRow(
            title=title,
            active=self._config.get(key, default),
        )
        row.connect("notify::active", self._set_config(key))
        group.add(row)

    def _set_config(self, key: str) -> Callable:
        def _handler(_widget: Any, *_args: Any) -> None:
            pass  # Value is read in _save

        return _handler

    def _save(self) -> None:
        self._on_save(dict(self._config))
        self.close()
