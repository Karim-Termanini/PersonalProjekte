"""HypeDevHome — Maintenance Pulse Dashboard Widget.

A visual dashboard showing system health and maintenance status.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402

log = logging.getLogger(__name__)


class PulseDashboard(Gtk.Box):
    """Real-time maintenance 'Pulse' dashboard with container health metrics."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        state = AppState.get()
        self._manager = state.pulse_manager
        if not self._manager:
            from core.maintenance.pulse_manager import PulseManager
            from core.setup.host_executor import HostExecutor

            self._manager = PulseManager(HostExecutor())
            state.pulse_manager = self._manager
        self._task_rows: dict[str, Adw.ActionRow] = {}
        self._build_ui()

        # Start refresh timer (5 seconds)
        from gi.repository import GLib

        self._timer_id = GLib.timeout_add(5000, self._refresh_ui)

    def do_unrealize(self) -> None:
        if getattr(self, "_timer_id", 0):
            GLib.source_remove(self._timer_id)
            self._timer_id = 0
        Gtk.Box.do_unrealize(self)

    def _build_ui(self) -> None:
        """Assemble the dashboard layout."""
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(18)
        self.set_margin_bottom(18)
        self.set_spacing(24)

        # 1. Overall Health Section
        health_group = Adw.PreferencesGroup(title="System Overview")

        self._status_row = Adw.ActionRow(
            title="System Status",
            subtitle="Overall environment health score",
            icon_name="utilities-system-monitor-symbolic",
        )

        self._score_label = Gtk.Label(label="--%")
        self._score_label.add_css_class("title-1")
        self._score_label.set_margin_end(12)
        self._status_row.add_suffix(self._score_label)

        health_group.add(self._status_row)
        self.append(health_group)

        # 2. Real-time Metrics Section (The "Pulse")
        metrics_group = Adw.PreferencesGroup(title="System Pulse")

        # CPU Metric
        self._cpu_row = Adw.ActionRow(title="CPU Usage", icon_name="computer-symbolic")
        self._cpu_bar = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        self._cpu_bar.add_css_class("os-bar")  # Custom CSS for thickness
        self._cpu_label = Gtk.Label(label="0.0%", css_classes=["numeric", "dim-label"])
        self._cpu_row.add_suffix(self._cpu_bar)
        self._cpu_row.add_suffix(self._cpu_label)
        metrics_group.add(self._cpu_row)

        # RAM Metric
        self._ram_row = Adw.ActionRow(title="Memory", icon_name="ram-symbolic")
        self._ram_bar = Gtk.ProgressBar(hexpand=True, valign=Gtk.Align.CENTER)
        self._ram_bar.add_css_class("os-bar")
        self._ram_label = Gtk.Label(label="0.0%", css_classes=["numeric", "dim-label"])
        self._ram_row.add_suffix(self._ram_bar)
        self._ram_row.add_suffix(self._ram_label)
        metrics_group.add(self._ram_row)

        self.append(metrics_group)

        # 3. Infrastructure Layers
        infra_group = Adw.PreferencesGroup(title="Infrastructure Status")

        self._container_health_row = Adw.ActionRow(
            title="Containers",
            subtitle="Checking services...",
            icon_name="docker-symbolic",
        )
        infra_group.add(self._container_health_row)

        self._snapshot_status_row = Adw.ActionRow(
            title="Guardian Layers",
            subtitle="Checking snapshots...",
            icon_name="security-high-symbolic",
        )
        infra_group.add(self._snapshot_status_row)

        self.append(infra_group)

        tasks_group = Adw.PreferencesGroup(
            title="Maintenance Tasks", description="Tasks to keep your dev environment clean"
        )

        if not self._manager:
            self.append(tasks_group)
            return

        for task in self._manager.get_tasks():
            row = Adw.ActionRow(
                title=task["name"], subtitle=f"Status: {task['status']}", icon_name=task["icon"]
            )

            # Action button
            run_btn = Gtk.Button(
                label="Run" if task["status"] != "Completed" else "Again",
                valign=Gtk.Align.CENTER,
                css_classes=["flat"],
            )
            if task["status"] == "Pending":
                run_btn.add_css_class("suggested-action")

            run_btn.connect("clicked", self._on_run_clicked, task["id"])
            row.add_suffix(run_btn)

            tasks_group.add(row)
            self._task_rows[task["id"]] = row

        self.append(tasks_group)

    def _refresh_ui(self) -> bool:
        """Update the dashboard with latest manager data."""
        if not self._manager:
            return True

        summary = self._manager.get_summary()
        self._status_row.set_subtitle(f"Last check: {summary['last_check']}")

        score = summary["overall_score"]
        self._score_label.set_label(f"{score}%")

        # Update styling
        self._score_label.remove_css_class("success")
        self._score_label.remove_css_class("warning")
        self._score_label.remove_css_class("error")

        if score > 80:
            self._score_label.add_css_class("success")
        elif score > 50:
            self._score_label.add_css_class("warning")
        else:
            self._score_label.add_css_class("error")

        # Update telemetry bars and labels
        telemetry = summary.get("telemetry", {})
        cpu_val = telemetry.get("cpu", 0)
        ram_val = telemetry.get("ram", 0)

        self._cpu_bar.set_fraction(cpu_val / 100.0)
        self._cpu_label.set_label(f"{cpu_val:.1f}%")

        self._ram_bar.set_fraction(ram_val / 100.0)
        ram_used = telemetry.get("ram_used_gb", 0)
        ram_total = telemetry.get("ram_total_gb", 1)
        self._ram_label.set_label(f"{ram_used:.1f} / {ram_total:.1f} GB")

        # Update container health
        self._update_container_health(summary)

        # Update snapshot status
        self._update_snapshot_status()

        # Update individual task statuses
        for task in self._manager.get_tasks():
            if task["id"] in self._task_rows:
                row = self._task_rows[task["id"]]
                row.set_subtitle(f"Status: {task['status']}")

        return True  # Continue timer

    def _update_container_health(self, summary: dict[str, Any]) -> None:
        """Update container health information."""
        if not self._manager:
            return

        container_summary = summary.get("telemetry", {}).get("containers", {})

        total_containers = container_summary.get("total_containers", 0)
        running_containers = container_summary.get("running_containers", 0)

        if total_containers == 0:
            self._container_health_row.set_subtitle("No containers found")
            self._container_health_row.set_icon_name("dialog-information-symbolic")
        else:
            health_details = self._manager.get_container_health_details()
            unhealthy_count = len(health_details.get("unhealthy_containers", []))
            high_resource_count = len(health_details.get("high_resource_containers", []))

            if unhealthy_count == 0 and high_resource_count == 0:
                self._container_health_row.set_subtitle(
                    f"{running_containers}/{total_containers} running - Healthy"
                )
                self._container_health_row.set_icon_name("emblem-ok-symbolic")
            elif unhealthy_count > 0:
                self._container_health_row.set_subtitle(
                    f"{running_containers}/{total_containers} running - {unhealthy_count} unhealthy"
                )
                self._container_health_row.set_icon_name("dialog-warning-symbolic")
            else:
                self._container_health_row.set_subtitle(
                    f"{running_containers}/{total_containers} running - {high_resource_count} high resource"
                )
                self._container_health_row.set_icon_name("dialog-information-symbolic")

    def _update_snapshot_status(self) -> None:
        """Update snapshot status information."""
        try:
            app_state = AppState.get()
            snapshot_manager = app_state.snapshot_manager

            if snapshot_manager:
                # Get snapshot status asynchronously
                import asyncio

                async def get_snapshot_info():
                    snapshots = await snapshot_manager.list_snapshots()
                    encrypted_count = sum(1 for s in snapshots if s.encrypted)
                    total_size = sum(s.size_bytes for s in snapshots)

                    # Format size
                    if total_size > 1024 * 1024 * 1024:  # GB
                        size_str = f"{total_size / (1024 * 1024 * 1024):.1f} GB"
                    elif total_size > 1024 * 1024:  # MB
                        size_str = f"{total_size / (1024 * 1024):.1f} MB"
                    else:  # KB
                        size_str = f"{total_size / 1024:.1f} KB"

                    return len(snapshots), encrypted_count, size_str

                # Run async task
                # Run async task via App
                from gi.repository import Gtk

                app_instance = Gtk.Application.get_default()
                if app_instance and hasattr(app_instance, "enqueue_task"):
                    # Use cast or Any to satisfy MyPy for dynamic method
                    app_any: Any = app_instance
                    app_any.enqueue_task(get_snapshot_info(), callback=self._on_snapshot_info_done)
                else:

                    def run_fallback() -> bool:
                        self._snapshot_refresh_task = asyncio.create_task(get_snapshot_info())
                        return False

                    GLib.idle_add(run_fallback)
            else:
                self._snapshot_status_row.set_subtitle("Snapshot manager not available")
                self._snapshot_status_row.set_icon_name("dialog-error-symbolic")

        except Exception as e:
            log.error("Failed to get snapshot status: %s", e)
            self._snapshot_status_row.set_subtitle("Error checking snapshots")
            self._snapshot_status_row.set_icon_name("dialog-error-symbolic")

    def _on_snapshot_info_done(self, future) -> None:
        """Callback when snapshot info future is ready."""
        try:
            snapshot_count, encrypted_count, size_str = future.result()

            if snapshot_count == 0:
                self._snapshot_status_row.set_subtitle("No snapshots found")
                self._snapshot_status_row.set_icon_name("dialog-information-symbolic")
            else:
                status_text = (
                    f"{snapshot_count} snapshots ({encrypted_count} encrypted) - {size_str}"
                )
                self._snapshot_status_row.set_subtitle(status_text)

                # Set icon based on encryption status
                if encrypted_count == snapshot_count:
                    self._snapshot_status_row.set_icon_name("security-high-symbolic")
                elif encrypted_count > 0:
                    self._snapshot_status_row.set_icon_name("security-medium-symbolic")
                else:
                    self._snapshot_status_row.set_icon_name("security-low-symbolic")

        except Exception as e:
            log.error("Error processing snapshot info: %s", e)
            self._snapshot_status_row.set_subtitle("Error loading snapshot info")
            self._snapshot_status_row.set_icon_name("dialog-error-symbolic")

    def _on_run_clicked(self, _btn: Gtk.Button, task_id: str) -> None:
        """Handle task run button."""

        from core.state import AppState

        async def run_and_refresh():
            if not self._manager:
                return
            success = await self._manager.run_task(task_id)
            if success:
                self._refresh_ui()
                # Notify via Toast
                bus = AppState.get().event_bus
                if bus:
                    bus.emit(
                        "ui.notification",
                        message=f"Task '{task_id}' completed successfully",
                        type="success",
                    )

        # Run via App
        from gi.repository import Gtk

        app_instance = Gtk.Application.get_default()
        if app_instance and hasattr(app_instance, "enqueue_task"):
            app_any: Any = app_instance
            app_any.enqueue_task(run_and_refresh())
        else:
            self._run_and_refresh_task = asyncio.create_task(run_and_refresh())
        log.info("Triggered task: %s", task_id)
