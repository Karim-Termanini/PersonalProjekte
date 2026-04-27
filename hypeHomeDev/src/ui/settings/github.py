"""HypeDevHome — GitHub settings panel.

Settings panel for GitHub integration configuration.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import TYPE_CHECKING

from gi.repository import Adw, GLib, Gtk

from config.defaults import DEFAULT_GITHUB_REFRESH_INTERVAL
from core.github.auth import get_auth_manager
from core.state import AppState
from ui.dialogs.github_auth import GitHubAuthDialog

if TYPE_CHECKING:
    from config.manager import ConfigManager

log = logging.getLogger(__name__)


class GitHubSettingsPage(Adw.PreferencesPage):
    """GitHub integration settings page."""

    def __init__(self, config_manager: ConfigManager) -> None:
        """Initialize the GitHub settings page."""
        super().__init__(
            title="GitHub",
            icon_name="github-symbolic",
        )

        self._config = config_manager
        self._suppress_refresh_combo = False
        self._auth_manager = get_auth_manager()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup settings page UI."""
        # Authentication group
        auth_group = Adw.PreferencesGroup(
            title="Authentication",
            description="Configure GitHub Personal Access Token",
        )

        # Auth status row
        self._auth_status_row = Adw.ActionRow(
            title="GitHub Status",
            subtitle="Not connected",
        )

        # Auth button
        self._auth_button = Gtk.Button()
        self._auth_button.connect("clicked", self._on_auth_button_clicked)
        self._auth_status_row.add_suffix(self._auth_button)

        auth_group.add(self._auth_status_row)

        # Refresh settings group
        refresh_group = Adw.PreferencesGroup(
            title="Refresh Settings",
            description="Configure how often GitHub data is updated",
        )

        # Refresh interval row
        refresh_row = Adw.ActionRow(
            title="Refresh Interval",
            subtitle="How often to update GitHub data",
        )

        self._refresh_combo = Gtk.ComboBoxText()
        self._refresh_combo.append("15", "15 seconds")
        self._refresh_combo.append("30", "30 seconds")
        self._refresh_combo.append("60", "1 minute")
        self._refresh_combo.append("300", "5 minutes")
        self._refresh_combo.connect("changed", self._on_refresh_interval_changed)

        refresh_row.add_suffix(self._refresh_combo)
        refresh_group.add(refresh_row)

        # Cache management group
        cache_group = Adw.PreferencesGroup(
            title="Cache Management",
            description="Manage cached GitHub data",
        )

        # Clear cache row
        cache_row = Adw.ActionRow(
            title="Clear Cache",
            subtitle="Remove cached GitHub data",
        )

        clear_button = Gtk.Button(label="Clear Now")
        clear_button.add_css_class("destructive-action")
        clear_button.connect("clicked", self._on_clear_cache)
        cache_row.add_suffix(clear_button)

        cache_group.add(cache_row)

        # API usage group
        api_group = Adw.PreferencesGroup(
            title="API Usage",
            description="GitHub API rate limit information",
        )

        # Rate limit row
        self._rate_limit_row = Adw.ActionRow(
            title="Rate Limit",
            subtitle="Loading...",
        )

        api_group.add(self._rate_limit_row)

        # Add groups to page
        self.add(auth_group)
        self.add(refresh_group)
        self.add(cache_group)
        self.add(api_group)

        self._sync_refresh_combo_from_config()

        # Update initial state
        self._update_auth_state()

        self.connect("map", self._on_page_mapped)

    def _on_page_mapped(self, *_args: object) -> None:
        self._schedule_rate_limit_refresh()

    def _sync_refresh_combo_from_config(self) -> None:
        """Load combo from config without emitting events."""
        interval = int(
            self._config.get("github_refresh_interval", DEFAULT_GITHUB_REFRESH_INTERVAL)
        )
        if str(interval) not in ("15", "30", "60", "300"):
            interval = 30
        self._suppress_refresh_combo = True
        self._refresh_combo.set_active_id(str(interval))
        self._suppress_refresh_combo = False

    def _update_auth_state(self) -> None:
        """Update authentication state display."""
        is_authenticated = self._auth_manager.is_authenticated()

        if is_authenticated:
            username = self._auth_manager.get_username()
            self._auth_manager.get_scopes()

            self._auth_status_row.set_subtitle(f"Connected as {username}")
            self._auth_button.set_label("Disconnect")
            self._auth_button.remove_css_class("suggested-action")
            self._auth_button.add_css_class("destructive-action")
            self._schedule_rate_limit_refresh()
        else:
            self._auth_status_row.set_subtitle("Not connected")
            self._auth_button.set_label("Connect")
            self._auth_button.remove_css_class("destructive-action")
            self._auth_button.add_css_class("suggested-action")
            self._rate_limit_row.set_subtitle("Not connected — add a token to see API limits")

    def _on_auth_button_clicked(self, button: Gtk.Button) -> None:
        """Handle authentication button click."""
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None

        if self._auth_manager.is_authenticated():
            # Disconnect
            msg_dialog = Adw.MessageDialog(
                transient_for=parent,
                heading="Disconnect from GitHub?",
                body="This will remove your GitHub token from the app. "
                "GitHub widgets will stop working until you reconnect.",
            )
            msg_dialog.add_response("cancel", "Cancel")
            msg_dialog.add_response("disconnect", "Disconnect")
            msg_dialog.set_response_appearance("disconnect", Adw.ResponseAppearance.DESTRUCTIVE)
            msg_dialog.connect("response", self._on_disconnect_response)
            msg_dialog.present()
        else:
            # Connect
            auth_dialog = GitHubAuthDialog(parent=parent)
            auth_dialog.present()
            auth_dialog.connect("close-request", self._on_auth_dialog_closed)

    def _on_disconnect_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        """Handle disconnect dialog response."""
        if response == "disconnect":
            success = self._auth_manager.clear_credentials()
            if success:
                log.info("GitHub credentials cleared")
                self._update_auth_state()
            else:
                log.error("Failed to clear GitHub credentials")

    def _on_auth_dialog_closed(self, dialog) -> None:
        """Handle authentication dialog closing."""
        self._update_auth_state()

    def _on_refresh_interval_changed(self, combo: Gtk.ComboBoxText) -> None:
        """Handle refresh interval change."""
        if self._suppress_refresh_combo:
            return
        interval_id = combo.get_active_id()
        if not interval_id:
            return
        interval = float(int(interval_id))
        self._config.set("github_refresh_interval", interval)
        log.info("GitHub refresh interval saved: %s s", interval)
        state = AppState.get()
        if state.event_bus:
            state.event_bus.emit("github.refresh_interval", seconds=interval)

    def _on_clear_cache(self, button: Gtk.Button) -> None:
        """Handle clear cache button click."""
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None

        dialog = Adw.MessageDialog(
            transient_for=parent,
            heading="Clear GitHub Cache?",
            body="This will remove all cached GitHub data. "
            "The next refresh will fetch fresh data from GitHub API.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("clear", "Clear Cache")
        dialog.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.connect("response", self._on_clear_cache_response)
        dialog.present()

    def _on_clear_cache_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        """Handle clear cache dialog response."""
        if response != "clear":
            return

        app = Gtk.Application.get_default()
        if not app or not hasattr(app, "enqueue_task"):
            log.warning("Cannot clear GitHub cache: no background loop")
            return

        async def clear_all() -> None:
            from core.github.cache import get_github_disk_cache
            from core.github.client import get_client

            client = await get_client()
            await client.clear_cache()
            get_github_disk_cache().clear()

        def _done(fut: concurrent.futures.Future[None]) -> None:
            def ui() -> None:
                try:
                    fut.result()
                    toast = Adw.Toast(
                        title="GitHub cache cleared",
                        timeout=2,
                    )
                    root = self.get_root()
                    if root is not None and hasattr(root, "add_toast"):
                        root.add_toast(toast)  # type: ignore[attr-defined, union-attr]
                except Exception as e:
                    log.error("GitHub cache clear failed: %s", e)

            GLib.idle_add(ui)

        app.enqueue_task(clear_all(), callback=_done)

    def _schedule_rate_limit_refresh(self) -> None:
        """Fetch /rate_limit and update the row (async)."""
        if not self._auth_manager.is_authenticated():
            return

        app = Gtk.Application.get_default()
        if not app or not hasattr(app, "enqueue_task"):
            self._rate_limit_row.set_subtitle("Unavailable")
            return

        async def probe_limits():
            from core.github.client import get_client

            client = await get_client()
            await client.probe_rate_limits()
            return client.get_rate_limits()

        def _done(fut: concurrent.futures.Future[object]) -> None:
            def ui() -> None:
                try:
                    limits = fut.result()
                    if not isinstance(limits, dict):
                        self._rate_limit_row.set_subtitle("No data")
                        return
                    core = limits.get("core")
                    if core is None:
                        self._rate_limit_row.set_subtitle("No core limit data")
                        return
                    reset_s = ""
                    if core.reset_at:
                        reset_s = core.reset_at.strftime("%H:%M UTC")
                    self._rate_limit_row.set_subtitle(
                        f"{core.remaining} / {core.limit} remaining · resets ~{reset_s}"
                    )
                except Exception as e:
                    self._rate_limit_row.set_subtitle(str(e)[:120])

            GLib.idle_add(ui)

        app.enqueue_task(probe_limits(), callback=_done)
