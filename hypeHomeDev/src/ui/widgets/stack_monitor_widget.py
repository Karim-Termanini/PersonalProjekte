"""HypeDevHome — Isolated Stacks Monitoring Widget.

Displays a live list of containers (Distrobox/Toolbx) with resource usage,
status indicators, and quick lifecycle controls.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from app import HypeDevHomeApp

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from core.setup.terminal import TerminalLauncher  # noqa: E402
from core.state import AppState  # noqa: E402
from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402
from ui.widgets.status_indicator import StatusIndicator, StatusLevel  # noqa: E402

log = logging.getLogger(__name__)


class StackRow(Adw.ActionRow):
    """An interactive row for a single container stack."""

    def __init__(self, stack_data: dict[str, Any]) -> None:
        super().__init__(title=stack_data["name"])
        self.set_subtitle(f"{stack_data['engine'].title()} • {stack_data['image']}")

        self._name = stack_data["name"]
        self._engine = stack_data["engine"]
        self._background_tasks: set[concurrent.futures.Future[Any]] = set()

        # 1. Status Indicator
        is_running = "Up" in stack_data["status"] or "running" in stack_data["status"]
        level = StatusLevel.SUCCESS if is_running else StatusLevel.NEUTRAL
        self._status = StatusIndicator(level=level)
        self.add_prefix(self._status)

        # Health indicator (initially hidden)
        self._health_indicator = StatusIndicator(level=StatusLevel.NEUTRAL, size=16)
        self._health_indicator.set_tooltip_text("Health: Unknown")
        self._health_indicator.set_visible(False)
        self.add_prefix(self._health_indicator)

        # 2. Resource Stats (CPU/Mem)
        self._stats_label = Gtk.Label(label="", css_classes=["caption", "dim-label"])
        self._update_stats(stack_data)
        self.add_suffix(self._stats_label)

        # 3. Actions
        prefix_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # Terminal Button
        self._term_btn = Gtk.Button(
            icon_name="utilities-terminal-symbolic", tooltip_text="Enter Terminal"
        )
        self._term_btn.set_has_frame(False)
        self._term_btn.connect("clicked", self._on_terminal_clicked)
        prefix_box.append(self._term_btn)

        # Snapshot Button
        self._snap_btn = Gtk.Button(
            icon_name="camera-photo-symbolic", tooltip_text="Manage Snapshots"
        )
        self._snap_btn.set_has_frame(False)
        self._snap_btn.connect("clicked", self._on_snapshots_clicked)
        prefix_box.append(self._snap_btn)

        # Power Toggle
        self._power_btn = Gtk.Button(
            icon_name="media-playback-stop-symbolic"
            if is_running
            else "media-playback-start-symbolic"
        )
        self._power_btn.set_has_frame(False)
        self._power_btn.connect("clicked", self._on_power_toggled)
        prefix_box.append(self._power_btn)

        self.add_suffix(prefix_box)

    def _update_stats(self, data: dict[str, Any]) -> None:
        cpu = data.get("cpu_percent", 0.0)
        mem = data.get("mem_usage_mb", 0.0)
        net = data.get("net_io_mb", 0.0)
        disk = data.get("block_io_mb", 0.0)

        # Primary label shows throughput (MB/s or current rate)
        stats_text = f"CPU: {cpu:.1f}%  RAM: {mem:.0f}MB"
        if net > 0 or disk > 0:
            stats_text += f"  Net: {net:.1f}MB/s  I/O: {disk:.1f}MB/s"

        self._stats_label.set_label(stats_text)

        # Tooltip shows cumulative data (if available in future tracking)
        # For now, we reuse the current values but the architecture is ready
        self._stats_label.set_tooltip_text(
            f"Network Total: {net:.1f} MB monitored\nDisk Total: {disk:.1f} MB monitored"
        )

    def _on_terminal_clicked(self, _btn: Gtk.Button) -> None:
        launcher = TerminalLauncher(AppState.get())
        launcher.launch_distrobox(self._name)

    def _on_snapshots_clicked(self, _btn: Gtk.Button) -> None:
        from ui.dialogs.snapshots import SnapshotManagementDialog

        win = self.get_root()
        if isinstance(win, Gtk.Window):
            dialog = SnapshotManagementDialog(self._name, transient_for=win)
            dialog.present()

    def _on_power_toggled(self, _btn: Gtk.Button) -> None:
        app_state = AppState.get()
        if not app_state.environment_manager:
            return

        is_running = "Up" in self._status.level.value or self._status.level == StatusLevel.SUCCESS

        if is_running:
            app = cast("HypeDevHomeApp", Gio.Application.get_default())
            task: concurrent.futures.Future[Any] | None = app.enqueue_task(
                app_state.environment_manager.stop_container(self._name, self._engine)
            )
        else:
            app = cast("HypeDevHomeApp", Gio.Application.get_default())
            task = app.enqueue_task(
                app_state.environment_manager.start_container(self._name, self._engine)
            )

        if task:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)


class StackMonitorWidget(DashboardWidget):
    """Dashboard widget that lists and monitors isolated stacks."""

    widget_title = "Isolated Stacks"
    widget_icon = "container-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            widget_id="stack_monitor",
            title=self.widget_title,
            icon_name=self.widget_icon,
            **kwargs,
        )
        self._rows: dict[str, StackRow] = {}

    def build_ui(self) -> None:
        """Build the stack list container."""
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")

        # Empty state
        self._empty_label = Gtk.Label(
            label="No stacks detected", css_classes=["dim-label"], margin_top=20, margin_bottom=20
        )
        self._list_box.append(self._empty_label)

        self.append(self._list_box)

    def on_activate(self) -> None:
        """Subscribe to stack updates."""
        super().on_activate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.subscribe("sysmon.stacks.update", self._on_stacks_update)
            event_bus.subscribe("maint.snapshot.health_check", self._on_health_update)

    def on_deactivate(self) -> None:
        """Unsubscribe from updates."""
        super().on_deactivate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.unsubscribe("sysmon.stacks.update", self._on_stacks_update)
            event_bus.unsubscribe("maint.snapshot.health_check", self._on_health_update)

    def _on_stacks_update(self, stacks: list[dict[str, Any]]) -> None:
        """Handle real-time stack updates from the monitor."""
        GLib.idle_add(self._update_list, stacks)

    def _on_health_update(self, snapshot_id: str, results: list[Any]) -> None:
        """Handle health check results from snapshot restoration."""
        # Extract container name from snapshot_id (format: container_name_timestamp)
        container_name = snapshot_id.split("_")[0]
        GLib.idle_add(self._update_health, container_name, results)

    def _update_list(self, stacks: list[dict[str, Any]]) -> None:
        """Update the UI with fresh stack data."""
        if not stacks:
            self._empty_label.set_visible(True)
        else:
            self._empty_label.set_visible(False)

        # Keep track of existing stacks to handle removals
        updated_names = {s["name"] for s in stacks}

        # Remove old rows
        for name in list(self._rows.keys()):
            if name not in updated_names:
                row = self._rows.pop(name)
                self._list_box.remove(row)

        # Update or add new rows
        for stack in stacks:
            name = stack["name"]
            if name in self._rows:
                # Update existing (status and stats)
                row = self._rows[name]
                is_running = "Up" in stack["status"] or "running" in stack["status"]
                row._status.level = StatusLevel.SUCCESS if is_running else StatusLevel.NEUTRAL
                row._power_btn.set_icon_name(
                    "media-playback-stop-symbolic"
                    if is_running
                    else "media-playback-start-symbolic"
                )
                row._update_stats(stack)
            else:
                # Add new
                row = StackRow(stack)
                self._rows[name] = row
                self._list_box.append(row)

    def _update_health(self, container_name: str, results: list[Any]) -> None:
        """Update health indicator for a specific container."""
        if container_name not in self._rows:
            return

        row = self._rows[container_name]

        # Determine overall health status
        all_healthy = True
        any_failed = False

        for result in results:
            if hasattr(result, "status"):
                status_str = str(result.status)
                if "FAILED" in status_str:
                    any_failed = True
                    all_healthy = False
                elif "DEGRADED" in status_str:
                    all_healthy = False

        if any_failed:
            row._health_indicator.level = StatusLevel.ERROR
            row._health_indicator.set_tooltip_text("Health: Failed - Check container status")
        elif not all_healthy:
            row._health_indicator.level = StatusLevel.WARNING
            row._health_indicator.set_tooltip_text("Health: Degraded - Some checks failed")
        else:
            row._health_indicator.level = StatusLevel.SUCCESS
            row._health_indicator.set_tooltip_text("Health: Healthy - All checks passed")

        row._health_indicator.set_visible(True)
