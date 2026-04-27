import asyncio
import concurrent.futures
import logging
import threading
import time
from collections.abc import Callable, Coroutine
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from config.manager import ConfigManager  # noqa: E402
from config.theme import ThemeManager  # noqa: E402
from core.maintenance.logger import ActivityLogger  # noqa: E402
from core.maintenance.manager import SnapshotManager  # noqa: E402
from core.maintenance.pulse_manager import PulseManager  # noqa: E402
from core.maintenance.storage import LocalStorageProvider  # noqa: E402
from core.maintenance.sync_tracker import HypeSyncStatusTracker  # noqa: E402
from core.monitoring.github_monitor import GitHubMonitor  # noqa: E402
from core.monitoring.stacks import StackMonitor  # noqa: E402
from core.monitoring.system import SystemMonitor  # noqa: E402
from core.setup.env_vars import EnvVarEngine  # noqa: E402
from core.setup.environments import EnvironmentManager  # noqa: E402
from core.setup.git_ops import GitOperations  # noqa: E402
from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.hosts import HostFileManager  # noqa: E402
from core.setup.sync_manager import SyncManager  # noqa: E402
from core.state import AppState  # noqa: E402
from ui.about import AboutDialog  # noqa: E402
from ui.settings import SettingsDialog  # noqa: E402
from ui.widgets.init_registry import register_built_in_widgets  # noqa: E402
from ui.window import HypeDevHomeWindow  # noqa: E402

log = logging.getLogger(__name__)

APP_ID = "com.github.hypedevhome"


class HypeDevHomeApp(Adw.Application):
    """Main application class for HypeDevHome."""

    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.config = ConfigManager()
        self.theme_manager: ThemeManager | None = None
        self._background_tasks: set[asyncio.Task[Any]] = set()
        self._loop_thread: threading.Thread | None = None
        log.debug("Application instance created (id=%s)", APP_ID)

    # ── Lifecycle callbacks ─────────────────────────────

    def do_startup(self) -> None:
        """Called once at application startup (before activate)."""
        Adw.Application.do_startup(self)

        # Load custom CSS (Agent A)
        self._load_custom_css()

        self._setup_asyncio_loop()

        # Initialize global state and event bus
        from core.events import EventBus

        app_state = AppState.get()
        app_state.event_bus = EventBus()
        log.debug("Global EventBus initialized")

        # Load configuration
        self.config.load()
        log.info("Configuration loaded from %s", self.config.path)

        # Initialize theme manager and apply theme
        self.theme_manager = ThemeManager(self.config)
        self.theme_manager.apply_theme()

        # Create actions
        self._create_actions()

        # Subscribe to theme change events
        from core.events import EventBus

        # Subscribe to theme change events
        if app_state.event_bus:
            app_state.event_bus.subscribe("theme_changed", self._on_theme_changed)

        # Register widgets and load dashboard layout
        register_built_in_widgets()
        app_state = AppState.get()
        app_state.config = self.config
        app_state.dashboard_layout = self.config.get("dashboard_layout", [])

        # Phase 5 utilities managers
        app_state.host_manager = HostFileManager(HostExecutor())
        app_state.env_var_engine = EnvVarEngine(HostExecutor())
        if not app_state.dashboard_layout:
            from config.defaults import DEFAULT_DASHBOARD_LAYOUT

            app_state.dashboard_layout = DEFAULT_DASHBOARD_LAYOUT

        # Initialize and start system monitor
        if app_state.event_bus:
            app_state.system_monitor = SystemMonitor(app_state.event_bus)
            if app_state.system_monitor:
                app_state.system_monitor.start()

        # Initialize and start github monitor
        if app_state.event_bus:
            gh_interval = float(self.config.get("github_refresh_interval", 30.0))
            self.github_monitor = GitHubMonitor(app_state.event_bus, interval=gh_interval)
            self.github_monitor.start()
            app_state.event_bus.subscribe(
                "github.refresh_interval", self._on_github_refresh_interval_changed
            )

        # Phase 6 Service Initialization
        executor = HostExecutor()
        git_ops = GitOperations(executor)
        sync_manager = SyncManager(executor, git_ops)

        env_manager = EnvironmentManager(executor)
        app_state.environment_manager = env_manager

        # Initialize monitors
        if app_state.event_bus:
            # Stack Monitor
            app_state.stack_monitor = StackMonitor(app_state.event_bus, env_manager)
            if app_state.stack_monitor:
                app_state.stack_monitor.start()

            # Sync Tracker
            app_state.sync_tracker = HypeSyncStatusTracker(
                sync_manager, git_ops, event_bus=app_state.event_bus
            )

            # Initial status pull
            def broadcast_wrapper() -> bool:
                if app_state and app_state.sync_tracker:
                    self.enqueue_task(app_state.sync_tracker.broadcast_status())
                return True

            GLib.timeout_add_seconds(30, broadcast_wrapper)

        # Persistence
        storage = LocalStorageProvider()
        app_state.snapshot_manager = SnapshotManager(
            env_manager, storage, event_bus=app_state.event_bus
        )

        # Pulse & Monitoring (Phase 7)
        pulse_manager = PulseManager(executor)
        app_state.pulse_manager = pulse_manager
        self.enqueue_task(pulse_manager.start())

        # Activity Logging (Final Phase 7 Step)
        activity_logger = ActivityLogger()
        app_state.activity_logger = activity_logger

        def status_for_event(event_name: str, payload: dict[str, Any]) -> str:
            if (
                "failed" in event_name
                or "error" in payload
                or "mismatch" in str(payload.get("details", "")).lower()
            ):
                return "failed"
            if "started" in event_name or "creating" in event_name:
                return "info"
            return "success"

        if app_state.event_bus:
            original_emit = app_state.event_bus.emit

            def emit_with_activity_logging(event_name: str, **kwargs: Any) -> None:
                if event_name.startswith("maint."):
                    activity_logger.log_event(
                        event_name,
                        status=status_for_event(event_name, kwargs),
                        **kwargs,
                    )
                original_emit(event_name, **kwargs)

            app_state.event_bus.emit = emit_with_activity_logging  # type: ignore[method-assign]

        log.debug("Application startup complete")

    def do_activate(self) -> None:
        """Called when the application is activated."""
        win = self.props.active_window
        if not win:
            win = HypeDevHomeWindow(config_manager=self.config, application=self)
            log.info("Main window created")
        win.present()

    def do_shutdown(self) -> None:
        """Called once at application shutdown."""
        log.info("Application shutting down")
        app_state = AppState.get()
        if app_state.system_monitor:
            app_state.system_monitor.stop()

        if hasattr(self, "github_monitor") and self.github_monitor:
            self.github_monitor.stop()

        if app_state.stack_monitor:
            app_state.stack_monitor.stop()

        loop = app_state.async_loop
        if loop and loop.is_running():
            log.debug("Stopping background asyncio loop")
            loop.call_soon_threadsafe(loop.stop)

        if self._loop_thread and self._loop_thread.is_alive():
            self._loop_thread.join(timeout=2.0)

        Adw.Application.do_shutdown(self)

    # ── Action handlers ─────────────────────────────────

    def _create_actions(self) -> None:
        """Create application actions."""
        # Settings action
        settings_action = Gio.SimpleAction.new("settings", None)
        settings_action.connect("activate", self._on_settings)
        self.add_action(settings_action)

        # About action
        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

        # Quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self._on_quit)
        self.add_action(quit_action)

        # Keyboard shortcuts
        self.set_accels_for_action("app.settings", ["<Ctrl>comma"])
        self.set_accels_for_action("app.quit", ["<Ctrl>q", "<Ctrl>w"])

        log.debug("Application actions created")

    def _on_settings(self, _action: Gio.SimpleAction, _param: None) -> None:
        """Handle settings action."""
        log.debug("Settings action triggered")
        win = self.props.active_window
        if win:
            settings_dialog = SettingsDialog(config_manager=self.config)
            settings_dialog.present(win)
        else:
            log.warning("No active window for settings dialog")

    def _on_about(self, _action: Gio.SimpleAction, _param: None) -> None:
        """Handle about action."""
        log.debug("About action triggered")
        win = self.props.active_window
        if win:
            about_dialog = AboutDialog(config_manager=self.config, transient_for=win)
            about_dialog.show()
        else:
            log.warning("No active window for about dialog")

    def _on_quit(self, _action: Gio.SimpleAction, _param: None) -> None:
        """Handle quit action."""
        log.debug("Quit action triggered")
        if not self.config.get("confirm_quit", True):
            self.quit()
            return

        win = self.props.active_window
        if not win:
            self.quit()
            return

        dialog = Adw.MessageDialog(
            transient_for=win,
            heading="Quit HypeDevHome?",
            body="You can disable this confirmation under Settings → Behavior.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("quit", "Quit")
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_quit_message_response)
        dialog.present()

    def _on_quit_message_response(self, dialog: Adw.MessageDialog, response: str) -> None:
        dialog.destroy()
        if response == "quit":
            self.quit()

    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change event."""
        log.debug("Theme change event received: %s", theme)
        if self.theme_manager:
            self.theme_manager.set_theme(theme)

    def _on_github_refresh_interval_changed(self, seconds: float, **_kwargs: Any) -> None:
        """Keep background GitHub monitor in sync with Settings."""
        gm = getattr(self, "github_monitor", None)
        if gm is not None:
            gm.interval = float(seconds)

    def _load_custom_css(self) -> None:
        """Load custom CSS from file."""
        import os

        # Get style file path relative to this file
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        css_path = os.path.join(curr_dir, "ui", "style", "gtk.css")

        if os.path.exists(css_path):
            provider = Gtk.CssProvider()
            provider.load_from_path(css_path)
            display = Gdk.Display.get_default()
            if display:
                Gtk.StyleContext.add_provider_for_display(
                    display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                )
                log.info("Custom CSS loaded from %s", css_path)
        else:
            log.warning("Custom CSS file not found at %s", css_path)

    # ── Asyncio Integration ─────────────────────────────

    def _setup_asyncio_loop(self) -> None:
        """Initialize the persistent background asyncio event loop."""
        loop = asyncio.new_event_loop()

        # Set up exception handler for the asyncio loop
        def handle_async_exception(
            loop: asyncio.AbstractEventLoop, context: dict[str, Any]
        ) -> None:
            """Handle unhandled exceptions in asyncio tasks."""
            exception = context.get("exception")
            message = context.get("message", "Unhandled exception in background task")

            if exception:
                log.error("Unhandled exception in asyncio task: %s", message, exc_info=exception)
                # Notify user via UI
                self._notify_background_error(f"Background task error: {message}", str(exception))
            else:
                log.error("Unhandled error in asyncio task: %s", message)
                self._notify_background_error("Background task error", message)

        loop.set_exception_handler(handle_async_exception)

        def run_loop() -> None:
            asyncio.set_event_loop(loop)
            try:
                loop.run_forever()
            except Exception as e:
                log.exception("Background asyncio loop crashed: %s", e)
                # Notify user about loop crash
                self._notify_background_error("Background service crashed", str(e))
            finally:
                # Cancel all pending tasks on shutdown
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.close()

        self._loop_thread = threading.Thread(
            target=run_loop, name="BackgroundAsyncLoop", daemon=True
        )

        # Set up thread exception handler
        def handle_thread_exception(args: threading.ExceptHookArgs) -> None:
            """Handle unhandled exceptions in threads."""
            log.error(
                "Unhandled exception in thread %s: %s",
                args.thread.name if args.thread else "unknown",
                args.exc_value,
                exc_info=args.exc_value,
            )
            # Notify user via UI
            self._notify_background_error(
                f"Thread error: {args.thread.name if args.thread else 'background thread'}",
                str(args.exc_value),
            )

        # Set the global thread exception handler
        threading.excepthook = handle_thread_exception

        self._loop_thread.start()

        # Store in global state
        AppState.get().async_loop = loop
        log.debug("Background asyncio loop initialized and threaded")

    def _notify_background_error(self, title: str, message: str) -> None:
        """Notify user about background errors via EventBus."""
        try:
            app_state = AppState.get()
            if app_state.event_bus:
                app_state.event_bus.emit(
                    "error.show-toast", message=f"{title}: {message}", type="error", timeout=15
                )
        except Exception:
            log.warning("Could not notify user about background error: EventBus not available")

    def enqueue_task(
        self,
        coro: Coroutine[Any, Any, Any],
        callback: Callable[[concurrent.futures.Future[Any]], None] | None = None,
    ) -> concurrent.futures.Future[Any] | None:
        """Schedule an asynchronous coroutine on the background event loop.

        Args:
            coro: The coroutine to execute.
            callback: Optional callback to execute when the task completes.
                      Must be safe to run within the async loop, or use GLib.idle_add
                      inside the callback if it touches the UI.

        Returns:
            The concurrent.futures.Future representing the execution, or None if the loop is dead.
        """
        loop = AppState.get().async_loop
        if not loop:
            log.error("enqueue_task called but async_loop is not set")
            coro.close()
            return None

        # Thread may have started run_forever() slightly after do_startup schedules tasks.
        deadline = time.monotonic() + 5.0
        while not loop.is_running() and time.monotonic() < deadline:
            time.sleep(0.01)

        if not loop.is_running():
            log.error("enqueue_task: background asyncio loop not running after wait")
            coro.close()
            return None

        future = asyncio.run_coroutine_threadsafe(coro, loop)
        if callback:
            future.add_done_callback(callback)
        return future
