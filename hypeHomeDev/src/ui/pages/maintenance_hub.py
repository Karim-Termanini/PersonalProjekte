"""HypeDevHome — Maintenance Hub & Guardian UI.

Consolidated page for system health monitoring, snapshot management,
and dev environment maintenance.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402
from ui.pages.base_page import BasePage  # noqa: E402

log = logging.getLogger(__name__)


class MaintenanceHubPage(BasePage):
    """Premium administrative hub for monitoring and Guardian management."""

    page_title = "Maintenance Hub"
    page_icon = "security-high-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._state = AppState.get()
        self._snapshot_manager = self._state.snapshot_manager
        self._pulse_manager = self._state.pulse_manager

    def build_content(self) -> None:
        """Construct the cohesive maintenance interface."""
        self._scroll = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER
        )

        # Use Adw.Clamp for a "Premium" responsive width center
        self._clamp = Adw.Clamp()
        self._clamp.set_maximum_size(800)
        self._clamp.set_tightening_threshold(600)

        self._page_container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=32, margin_top=32, margin_bottom=32
        )
        self._clamp.set_child(self._page_container)

        # 1. System Health Dashboard (Embed the new PulseDashboard)
        from ui.widgets.pulse_dashboard import PulseDashboard

        self._pulse_dash = PulseDashboard()
        self._page_container.append(self._pulse_dash)

        # 2. Guardian Snapshots
        self._build_guardian_section()

        # 3. Tasks & Maintenance
        self._build_tasks_section()

        self._scroll.set_child(self._clamp)
        self.append(self._scroll)

    def _build_health_highlights(self) -> None:
        # Replaced by PulseDashboard
        pass

    def _create_metric_widget(self, label: str, value: str) -> Gtk.Box:
        # Legacy
        return Gtk.Box()

    def _build_guardian_section(self) -> None:
        self._guardian_group = Adw.PreferencesGroup(
            title="Guardian Layers", description="Managed system and container snapshots"
        )

        self._snapshot_list = Gtk.ListBox()
        self._snapshot_list.add_css_class("boxed-list")
        self._snapshot_list.set_selection_mode(Gtk.SelectionMode.NONE)

        self._guardian_group.add(self._snapshot_list)
        self._page_container.append(self._guardian_group)

    def _build_tasks_section(self) -> None:
        group = Adw.PreferencesGroup(title="Active Tasks", description="Pending maintenance items")

        self._task_list = Gtk.ListBox()
        self._task_list.add_css_class("boxed-list")
        self._task_list.set_selection_mode(Gtk.SelectionMode.NONE)

        group.add(self._task_list)
        self._page_container.append(group)

    def on_shown(self) -> None:
        super().on_shown()
        self._refresh_data()
        rid = getattr(self, "_refresh_id", 0)
        if rid:
            GLib.source_remove(rid)
            self._refresh_id = 0
        self._refresh_id = GLib.timeout_add_seconds(5, self._refresh_data)

    def on_hidden(self) -> None:
        super().on_hidden()
        rid = getattr(self, "_refresh_id", 0)
        if rid:
            GLib.source_remove(rid)
            self._refresh_id = 0

    def _refresh_data(self) -> bool:
        """Update telemetry and list data."""
        # Update Tasks
        self._refresh_tasks()

        # Update Snapshots (Async)
        app_instance = Gtk.Application.get_default()
        if app_instance and hasattr(app_instance, "get_active_window"):
            win = app_instance.get_active_window()
            if win and hasattr(win, "get_application"):
                app = win.get_application()
                if app and hasattr(app, "enqueue_task"):
                    app_any: Any = app
                    app_any.enqueue_task(self._refresh_snapshots_async())
                else:
                    # Fallback or Test environment
                    def run_fallback() -> bool:
                        self._fallback_task = asyncio.create_task(self._refresh_snapshots_async())
                        return False

                    GLib.idle_add(run_fallback)

        return True

    def _update_metric(self, box: Gtk.Box, value: str) -> None:
        # Legacy
        pass

    def _refresh_tasks(self) -> None:
        # Clear existing
        while child := self._task_list.get_first_child():
            self._task_list.remove(child)

        if not self._pulse_manager:
            return

        tasks = self._pulse_manager.get_tasks()
        for task in tasks:
            row = Adw.ActionRow(title=task["name"], subtitle=task["status"])
            row.add_prefix(Gtk.Image.new_from_icon_name(task["icon"]))
            self._task_list.append(row)

    async def _refresh_snapshots_async(self) -> None:
        if not self._snapshot_manager:
            return

        snapshots = await self._snapshot_manager.list_snapshots()

        # UI update on main thread
        GLib.idle_add(self._update_snapshot_ui, snapshots)

    def _update_snapshot_ui(self, snapshots: list) -> None:
        while child := self._snapshot_list.get_first_child():
            self._snapshot_list.remove(child)

        if not snapshots:
            empty = Adw.ActionRow(title="No snapshots found")
            self._snapshot_list.append(empty)
            return

        for snap in snapshots:
            row = Adw.ActionRow(title=snap.name, subtitle=snap.timestamp)
            row.add_prefix(
                Gtk.Image.new_from_icon_name(
                    "security-high-symbolic" if snap.encrypted else "security-low-symbolic"
                )
            )
            # Add restore button
            btn = Gtk.Button.new_from_icon_name("edit-redo-symbolic")
            btn.add_css_class("flat")
            btn.set_tooltip_text("Restore Snapshot")
            row.add_suffix(btn)
            self._snapshot_list.append(row)
