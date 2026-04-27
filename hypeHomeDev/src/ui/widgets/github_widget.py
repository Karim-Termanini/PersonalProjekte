"""HypeDevHome — Base class for GitHub dashboard widgets.

Provides common functionality for GitHub widgets including:
- Authentication state checking
- Async data fetching from GitHub API
- Auto-refresh with configurable intervals
- Error handling for API failures
- Loading states
- Click-to-open-in-browser functionality
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from core.github.auth import get_auth_manager  # noqa: E402
from core.github.client import GitHubAPIError, GitHubAuthError, GitHubRateLimitError  # noqa: E402
from core.state import AppState  # noqa: E402
from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402

log = logging.getLogger(__name__)

GITHUB_REFRESH_INTERVAL_EVENT = "github.refresh_interval"


def _github_refresh_seconds_from_config() -> float:
    try:
        cfg = AppState.get().config
        if cfg is not None:
            v = cfg.get("github_refresh_interval")
            if v is not None:
                return float(v)
    except Exception:
        pass
    return GitHubWidget.DEFAULT_REFRESH_INTERVAL


def _fallback_asyncio_loop() -> asyncio.AbstractEventLoop:
    """Return the running loop, or create/set one for the main thread.

    Python 3.10+ does not create an implicit main-thread event loop. GTK apps
    normally use ``Application.enqueue_task``; unit tests hit the fallback path.
    """
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


class GitHubWidget(DashboardWidget):
    """Base class for all GitHub integration widgets.

    Extends DashboardWidget with GitHub-specific features:
    - Authentication verification
    - Async API data fetching
    - API error handling
    - Rate limit tracking
    - Browser link opening
    """

    # Default refresh interval for GitHub widgets (30 seconds)
    DEFAULT_REFRESH_INTERVAL = 30.0

    # Metadata for widget gallery
    widget_category = "GitHub"
    widget_description = "GitHub integration widget"

    def __init__(
        self,
        title: str,
        icon_name: str = "web-browser-symbolic",
        refresh_interval: float | None = None,
        widget_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the GitHub widget.

        Args:
            title: Human-readable title.
            icon_name: Icon name for the header.
            refresh_interval: Seconds between API refreshes, or ``None`` to use config
                ``github_refresh_interval`` (default 30s).
            widget_id: Optional widget ID (auto-generated if not provided).
        """
        # Initialize state before super().__init__ because it calls build_ui()
        self._auth_manager = get_auth_manager()
        self._is_authenticated = self._auth_manager.is_authenticated()
        self._api_error: str | None = None
        self._loading = True
        self._fetch_task: asyncio.Task | None = None

        # Auto-generate widget_id if not provided
        if widget_id is None:
            widget_id = self.__class__.__name__.lower()

        resolved_refresh = (
            float(refresh_interval)
            if refresh_interval is not None
            else _github_refresh_seconds_from_config()
        )

        # Create containers BEFORE super().__init__() (since it calls build_ui())
        self._auth_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        super().__init__(
            widget_id=widget_id,
            title=title,
            icon_name=icon_name,
            refresh_interval=resolved_refresh,
            **kwargs,
        )

    def build_ui(self) -> None:
        """Build the widget UI with loading/error states."""
        # Add containers to main box
        self.append(self._auth_container)
        self.append(self._content_container)

        # Update UI based on auth state
        self._update_auth_ui()

        # Start data fetch if authenticated
        if self._is_authenticated:
            self.start_data_fetch()

    def _update_auth_ui(self) -> None:
        """Update UI based on authentication state."""
        if not self._is_authenticated:
            self._show_not_configured()
        else:
            self._auth_container.set_visible(False)

    def show_loading(self) -> None:
        """Show loading state."""
        self._loading = True

        # Clear content
        while child := self._content_container.get_first_child():
            self._content_container.remove(child)

        # Add loading spinner
        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        spinner.set_halign(Gtk.Align.CENTER)
        self._content_container.append(spinner)

        loading_label = Gtk.Label(label="Loading...")
        loading_label.add_css_class("dim-label")
        self._content_container.append(loading_label)

    def show_error(self, message: str) -> None:
        """Show error message."""
        self._loading = False

        # Clear content
        while child := self._content_container.get_first_child():
            self._content_container.remove(child)

        # Error icon
        error_icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        error_icon.set_pixel_size(48)
        error_icon.add_css_class("error")
        self._content_container.append(error_icon)

        # Error message
        error_label = Gtk.Label(label=message)
        error_label.add_css_class("error")
        error_label.set_wrap(True)
        self._content_container.append(error_label)

        # Retry button
        retry_button = Gtk.Button(label="Retry")
        retry_button.add_css_class("suggested-action")
        retry_button.connect("clicked", lambda _btn: self.start_data_fetch())
        self._content_container.append(retry_button)

    def hide_loading(self) -> None:
        """Hide loading state."""
        self._loading = False

    async def fetch_github_data(self) -> Any:
        """Override this method to fetch data from GitHub API.

        Returns:
            Fetched data (type depends on widget implementation)
        """
        raise NotImplementedError("Subclasses must implement fetch_github_data()")

    def update_content(self, data: Any) -> None:
        """Override this method to update widget UI with fetched data.

        Args:
            data: Data returned from fetch_github_data()
        """
        raise NotImplementedError("Subclasses must implement update_content()")

    def start_data_fetch(self) -> None:
        """Start fetching data from GitHub API."""
        if not self._is_authenticated:
            return

        self.show_loading()

        # Create async task for data fetching via app loop
        app_instance = Gtk.Application.get_default()
        if app_instance and hasattr(app_instance, "enqueue_task"):
            from typing import Any, cast

            cast(Any, app_instance).enqueue_task(self._fetch_and_update())
        else:
            # Fallback when not running under the app (e.g. unit tests).
            loop = _fallback_asyncio_loop()
            self._fetch_task = loop.create_task(self._fetch_and_update())

    async def _fetch_and_update(self) -> None:
        """Fetch data and update UI asynchronously."""
        try:
            data = await self.fetch_github_data()

            # Update UI on main thread
            GLib.idle_add(self._update_ui_with_data, data)

        except GitHubAuthError:
            log.warning("GitHub auth failed for widget %s", self.title)
            GLib.idle_add(self.show_auth_error)
        except GitHubRateLimitError:
            GLib.idle_add(self.show_rate_limit_error)
        except GitHubAPIError as e:
            log.error("GitHub API error for %s: %s", self.title, e)
            err = str(e).lower()
            # Client wraps aiohttp failures as "Network error: ..." — real transport issues
            if err.startswith("network error:") or "timeout" in err:
                GLib.idle_add(self.show_network_error)
            else:
                GLib.idle_add(self.show_error, f"GitHub: {e}")
        except Exception as e:
            log.error("Error fetching GitHub data for %s: %s", self.title, e, exc_info=True)
            GLib.idle_add(self.show_error, f"Failed to load: {e}")

    def show_network_error(self) -> None:
        """Show network error message."""
        self.show_error("Network error. Please check your internet connection.")

    def show_rate_limit_error(self) -> None:
        """Show rate limit error message."""
        self.show_error("GitHub API rate limit exceeded. Try again later.")

    def show_auth_error(self) -> None:
        """Show authentication error message."""
        self.show_error("Authentication failed. Please check your GitHub token in Settings.")

    def _update_ui_with_data(self, data: Any) -> None:
        """Update UI with fetched data (called on main thread)."""
        self.hide_loading()
        self.update_content(data)

    def on_activate(self) -> None:
        """Called when widget is added to dashboard."""
        super().on_activate()
        state = AppState.get()
        if state.event_bus:
            state.event_bus.subscribe(
                GITHUB_REFRESH_INTERVAL_EVENT, self._on_global_github_refresh_interval
            )

    def _on_global_github_refresh_interval(self, seconds: float, **_kwargs: Any) -> None:
        self._refresh_interval = float(seconds)
        if self._refresh_timer_id > 0:
            self._stop_refresh_timer()
            if self._refresh_interval > 0:
                self._start_refresh_timer()

    def refresh(self) -> bool:
        """Periodic refresh from DashboardWidget timer."""
        if self._disposed:
            return False
        if self._is_authenticated:
            self.start_data_fetch()
        return True

    def on_deactivate(self) -> None:
        """Called when widget is removed from dashboard."""
        state = AppState.get()
        if state.event_bus:
            try:
                state.event_bus.unsubscribe(
                    GITHUB_REFRESH_INTERVAL_EVENT, self._on_global_github_refresh_interval
                )
            except Exception:
                log.debug("GitHub refresh unsubscribe skipped", exc_info=True)
        # Cancel any pending fetch tasks
        if self._fetch_task and not self._fetch_task.done():
            self._fetch_task.cancel()
        super().on_deactivate()

    def _show_not_configured(self) -> None:
        """Show message that GitHub authentication needs configuration."""
        # Clear auth container
        while child := self._auth_container.get_first_child():
            self._auth_container.remove(child)

        msg_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        msg_box.set_valign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("web-browser-symbolic")
        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        msg_box.append(icon)

        label = Gtk.Label(label="GitHub not configured")
        label.add_css_class("heading")
        msg_box.append(label)

        desc = Gtk.Label(label="Configure your GitHub token in Settings to enable GitHub widgets.")
        desc.add_css_class("dim-label")
        desc.set_wrap(True)
        msg_box.append(desc)

        # Button to open settings
        settings_btn = Gtk.Button(label="Open Settings")
        settings_btn.add_css_class("suggested-action")
        settings_btn.connect("clicked", self._on_open_settings)
        msg_box.append(settings_btn)

        self._auth_container.append(msg_box)
        self._auth_container.set_visible(True)
        self._content_container.set_visible(False)

    def _on_open_settings(self, _button: Gtk.Button) -> None:
        """Open application settings."""
        # This would trigger the settings dialog
        log.info("Open settings requested for GitHub widget")

    @staticmethod
    def _open_in_browser(url: str) -> None:
        """Open a URL in the default browser.

        Args:
            url: The URL to open.
        """
        try:
            launcher = Gio.AppInfo.launch_default_for_uri
            launcher(url, None)
        except GLib.Error as e:
            log.error("Failed to open URL %s: %s", url, e.message)

    def get_config(self) -> dict[str, Any]:
        """Return widget configuration for persistence."""
        config = super().get_config()
        config.update(
            {
                "github_widget": True,
            }
        )
        return config
