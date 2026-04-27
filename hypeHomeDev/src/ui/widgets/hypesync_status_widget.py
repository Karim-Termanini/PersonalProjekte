"""HypeDevHome — HypeSync Monitoring Widget.

Displays dotfiles drift status, secret injection health, and provides quick
access to manually trigger a synchronization.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402
from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402
from ui.widgets.status_indicator import StatusIndicator, StatusLevel  # noqa: E402

log = logging.getLogger(__name__)


class HypeSyncStatusWidget(DashboardWidget):
    """Dashboard widget for monitoring dotfile and secret synchronization."""

    widget_title = "HypeSync Status"
    widget_icon = "emblem-synchronizing-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            widget_id="hypesync_status",
            title=self.widget_title,
            icon_name=self.widget_icon,
            **kwargs,
        )
        self._background_tasks: set[asyncio.Task[Any]] = set()

    def build_ui(self) -> None:
        """Build the sync status UI."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(12)

        what = Gtk.Label(
            label=(
                "HypeSync is the name this app uses for syncing your dotfiles (and optionally "
                "secrets) from a Git repo into your home directory, and tracking drift. "
                "It is optional — ignore this card if you do not use that workflow."
            )
        )
        what.set_wrap(True)
        what.set_xalign(0)
        what.add_css_class("caption")
        what.add_css_class("dim-label")
        vbox.append(what)

        # 1. Dotfiles Status
        self._dotfiles_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._dot_indicator = StatusIndicator(
            level=StatusLevel.NEUTRAL, label="Dotfiles: Checking..."
        )
        self._dotfiles_row.append(self._dot_indicator)
        vbox.append(self._dotfiles_row)

        # 2. Secrets Status
        self._secrets_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._sec_indicator = StatusIndicator(
            level=StatusLevel.NEUTRAL, label="Secrets: Checking..."
        )
        self._secrets_row.append(self._sec_indicator)
        vbox.append(self._secrets_row)

        # 3. Drift Details
        self._drift_label = Gtk.Label(label="", css_classes=["caption", "dim-label"])
        self._drift_label.set_halign(Gtk.Align.START)
        vbox.append(self._drift_label)

        # 4. Action Button
        self._sync_btn = Gtk.Button(label="Sync Now")
        self._sync_btn.add_css_class("suggested-action")
        self._sync_btn.connect("clicked", self._on_sync_clicked)
        vbox.append(self._sync_btn)

        self.append(vbox)

    def on_activate(self) -> None:
        """Subscribe to HypeSync status updates."""
        super().on_activate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.subscribe("hypesync.status.update", self._on_status_update)
            # Request initial status
            app_state = AppState.get()
            if app_state.sync_tracker:
                # Request initial status via app loop
                app_instance = Gtk.Application.get_default()
                if app_instance and hasattr(app_instance, "enqueue_task"):
                    from typing import Any

                    cast(Any, app_instance).enqueue_task(app_state.sync_tracker.broadcast_status())
                else:
                    # Fallback for tests
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        task = loop.create_task(app_state.sync_tracker.broadcast_status())
                        self._background_tasks.add(task)
                        task.add_done_callback(self._background_tasks.discard)

    def on_deactivate(self) -> None:
        """Unsubscribe from updates."""
        super().on_deactivate()
        event_bus = AppState.get().event_bus
        if event_bus:
            event_bus.unsubscribe("hypesync.status.update", self._on_status_update)

    def _on_status_update(
        self,
        dotfiles_clean: bool = True,
        dotfiles_behind: bool = False,
        secrets_injected: bool = False,
        drift_details: str = "",
        **kwargs: Any,
    ) -> None:
        """Handle status update from the tracker."""
        GLib.idle_add(
            self._update_ui, dotfiles_clean, dotfiles_behind, secrets_injected, drift_details
        )

    def _update_ui(self, clean: bool, behind: bool, secrets: bool, drift: str) -> None:
        # Dotfiles
        if not clean:
            self._dot_indicator.level = StatusLevel.WARNING
            self._dot_indicator.label_text = "Dotfiles: Local Changes"
        elif behind:
            self._dot_indicator.level = StatusLevel.INFO
            self._dot_indicator.label_text = "Dotfiles: Update Available"
        else:
            self._dot_indicator.level = StatusLevel.SUCCESS
            self._dot_indicator.label_text = "Dotfiles: In Sync"

        # Secrets
        if secrets:
            self._sec_indicator.level = StatusLevel.SUCCESS
            self._sec_indicator.label_text = "Secrets: Injected"
        else:
            self._sec_indicator.level = StatusLevel.WARNING
            self._sec_indicator.label_text = "Secrets: Missing"

        self._drift_label.set_label(drift)

    def _on_sync_clicked(self, _btn: Gtk.Button) -> None:
        """Trigger a manual synchronization."""
        # TODO: Trigger full sync via SyncManager
        log.info("Manual synchronization triggered from widget")
        self._sync_btn.set_sensitive(False)
        GLib.timeout_add_seconds(3, lambda: self._on_sync_timeout())

    def _on_sync_timeout(self) -> bool:
        """Reset sync button sensitivity."""
        self._sync_btn.set_sensitive(True)
        return False
