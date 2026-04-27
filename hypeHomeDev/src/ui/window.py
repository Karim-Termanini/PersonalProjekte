"""HypeDevHome - Main application window.

Implements:
 - Adw.OverlaySplitView sidebar ↔ content layout (sidebar can be hidden/shown)
 - Window size/state persistence via ConfigManager
 - Keyboard shortcuts (Ctrl+1–8 main pages, Ctrl+Q, F11, Ctrl+,)
 - Hamburger menu with Settings / About / Quit
 - Lazy-loaded page lifecycle
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from config.manager import ConfigManager

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gio, Gtk  # noqa: E402

from core.state import AppState  # noqa: E402
from ui.about import AboutDialog  # noqa: E402
from ui.pages.base_page import BasePage  # noqa: E402
from ui.pages.dashboard import DashboardPage  # noqa: E402
from ui.pages.extensions import ExtensionsPage  # noqa: E402
from ui.pages.machine_setup import MachineSetupPage  # noqa: E402
from ui.pages.system_monitor import SystemMonitorPage  # noqa: E402
from ui.pages.maintenance_hub import MaintenanceHubPage  # noqa: E402
from ui.pages.utilities import UtilitiesPage  # noqa: E402
from ui.pages.welcome_dashboard import WelcomeDashboardPage  # noqa: E402
from ui.pages.workstation import WorkstationPage  # noqa: E402
from ui.settings import SettingsDialog  # noqa: E402
from ui.toast_manager import ToastManager  # noqa: E402

log = logging.getLogger(__name__)

DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 800

# ── Page registry ───────────────────────────────────────
# Each entry is (id, title, icon_name, PageClass).
_PAGE_REGISTRY: list[tuple[str, str, str, type[BasePage]]] = [
    # Welcome = default (new_plan.md Phase 1): wizards + health + servers overview.
    ("welcome", "Welcome", "user-home-symbolic", WelcomeDashboardPage),
    ("system", "System Monitor", "utilities-system-monitor-symbolic", SystemMonitorPage),
    ("workstation", "Tools", "preferences-desktop-apps-symbolic", WorkstationPage),
    ("dashboard", "Widgets", "view-grid-symbolic", DashboardPage),
    ("machine-setup", "Machine Setup", "computer-symbolic", MachineSetupPage),
    ("maintenance", "Maintenance Hub", "security-high-symbolic", MaintenanceHubPage),
    ("extensions", "Extensions", "application-x-addon-symbolic", ExtensionsPage),
    ("utilities", "Utilities", "applications-utilities-symbolic", UtilitiesPage),
]


class HypeDevHomeWindow(Adw.ApplicationWindow):
    """Primary window with sidebar navigation."""

    def __init__(self, config_manager: ConfigManager | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._pages: dict[str, BasePage] = {}
        self._current_page_id: str | None = None

        # ── Restore persisted size ──────────────────────
        state = AppState.get()
        self.config = config_manager or state.config

        # ── Global Notification Handler ──────────────────
        self._toast_manager = ToastManager.get(self)

        # Close window after user confirms quit (two-phase close-request)
        self._allow_close_without_confirm = False

        w = DEFAULT_WIDTH
        h = DEFAULT_HEIGHT
        if self.config:
            w = self.config.get("window_width", DEFAULT_WIDTH)
            h = self.config.get("window_height", DEFAULT_HEIGHT)
        self.set_default_size(w, h)
        self.set_title("HypeDevHome")

        # ── Build UI ────────────────────────────────────
        self._build_ui()
        self._setup_keyboard_shortcuts()
        self._setup_escape_key()

        # ── Persist size on close ───────────────────────
        self.connect("close-request", self._on_close_request)

        # ── Navigate to saved page or default ───────────
        start_page = "welcome"
        if self.config:
            start_page = self.config.get("last_page", "welcome")
        if start_page not in self._pages:
            start_page = "welcome"
        self.navigate_to(start_page)

        log.debug("Window initialised (%dx%d)", w, h)

    # ── UI construction ─────────────────────────────────

    def _build_ui(self) -> None:
        """Assemble the split-view layout."""

        # ── Sidebar list ────────────────────────────────
        self._sidebar_list = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["navigation-sidebar"],
        )
        self._sidebar_list.connect("row-selected", self._on_sidebar_row_selected)

        for page_id, title, icon_name, page_class in _PAGE_REGISTRY:
            row = self._make_sidebar_row(page_id, title, icon_name)
            self._sidebar_list.append(row)
            self._pages[page_id] = page_class()

        # ── Header bar (full-width, single bar) ─────────
        self._content_header = Adw.HeaderBar()
        self._content_title = Adw.WindowTitle(title="HypeDevHome", subtitle="")
        self._content_header.set_title_widget(self._content_title)

        self._header_actions_box = Gtk.Box(spacing=6)
        self._content_header.pack_start(self._header_actions_box)

        self._build_hamburger_menu()

        # ── Content stack ────────────────────────────────
        self._content_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
            vexpand=True,
            hexpand=True,
        )

        for page_id, page in self._pages.items():
            self._content_stack.add_named(page, page_id)

        # Eager-build primary pages so users never see spinner → full UI swap
        # (BasePage lazy init) on first open; see new_plan.md Welcome + System Monitor.
        for _eager_id in ("welcome", "system", "workstation"):
            pg = self._pages.get(_eager_id)
            if pg is not None:
                pg.ensure_built()

        # ── Sidebar rail ────────────────────────────────
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_size_request(68, -1)
        sidebar_box.add_css_class("sidebar-rail")

        sidebar_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vexpand=True,
        )
        sidebar_scroll.set_child(self._sidebar_list)
        sidebar_box.append(sidebar_scroll)

        # ── Body: sidebar | separator | content ─────────
        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # Required for Gtk.Stack + nested ScrolledWindow: without this, pages get
        # minimal height and inner scroll views never receive a real viewport.
        body.set_hexpand(True)
        body.set_vexpand(True)
        body.append(sidebar_box)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        body.append(self._content_stack)

        # ── Single ToolbarView wraps header + body ──────
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self._content_header)
        toolbar_view.set_content(body)

        # ── Toast Overlay ───────────────────────────────
        self._toast_overlay = Adw.ToastOverlay(child=toolbar_view)
        self.set_content(self._toast_overlay)

    def add_toast(self, toast: Adw.Toast) -> None:
        """Helper to show a toast in this window."""
        self._toast_overlay.add_toast(toast)

    def _make_sidebar_row(self, page_id: str, title: str, icon_name: str) -> Gtk.ListBoxRow:
        """Create a compact sidebar row with icon + tooltip."""
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0,
        )
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image(icon_name=icon_name)
        icon.set_pixel_size(20)
        box.append(icon)

        row = Gtk.ListBoxRow(child=box, name=page_id)
        row.set_tooltip_text(title)
        return row

    def _build_hamburger_menu(self) -> None:
        """Add a hamburger menu to the content header bar."""
        menu = Gio.Menu()
        menu.append("Settings", "app.settings")
        menu.append("Keyboard Shortcuts", "app.show-shortcuts")
        menu.append("About HypeDevHome", "app.about")
        menu.append("Quit", "app.quit")

        menu_button = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            menu_model=menu,
            tooltip_text="Main Menu",
            primary=True,
        )
        self._content_header.pack_end(menu_button)

    # ── Navigation ──────────────────────────────────────

    def navigate_to(self, page_id: str) -> None:
        """Switch to the page identified by *page_id*."""
        if page_id not in self._pages:
            log.warning("Unknown page: %s", page_id)
            return

        prev = self._current_page_id
        if prev == page_id:
            # Already active; skip redundant reset/hidden calls
            return

        if prev and prev in self._pages:
            self._pages[prev].on_hidden()

        self._current_page_id = page_id
        page = self._pages[page_id]
        page.on_shown()

        self._content_stack.set_visible_child_name(page_id)
        self._content_title.set_title("HypeDevHome")
        self._content_title.set_subtitle(page.get_window_title())
        self._update_header_actions(page)

        # Select matching sidebar row
        for i, (pid, *_) in enumerate(_PAGE_REGISTRY):
            if pid == page_id:
                row = self._sidebar_list.get_row_at_index(i)
                if row:
                    self._sidebar_list.select_row(row)
                break

        # Persist last page
        if self.config:
            self.config.set("last_page", page_id)

        log.debug("Navigated to '%s'", page_id)

    def navigate_to_workstation_section(self, section_id: str) -> bool:
        """Open Workstation and activate a subsection (``ai``, ``servers``, ``services``, …)."""
        self.navigate_to("workstation")
        page = self._pages.get("workstation")
        if page is None:
            return False
        go = getattr(page, "goto_section", None)
        if not callable(go):
            return False
        return bool(go(section_id))

    def _setup_escape_key(self) -> None:
        """Escape: back in nested views, or reveal sidebar when it was hidden on small screens."""
        ctrl = Gtk.EventControllerKey()
        ctrl.connect("key-pressed", self._on_escape_key_pressed)
        self.add_controller(ctrl)

    def _on_escape_key_pressed(
        self,
        _controller: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval != Gdk.KEY_Escape:
            return False
        return self._handle_escape_navigation()

    def _handle_escape_navigation(self) -> bool:
        """Return True if Escape was consumed."""
        if not self._current_page_id:
            return False
        page = self._pages.get(self._current_page_id)
        if page and page.handle_escape():
            return True
        return False

    def refresh_current_page_header(self) -> None:
        """Re-apply window title and header actions (e.g. nested navigation on one page)."""
        if not self._current_page_id:
            return
        page = self._pages.get(self._current_page_id)
        if not page:
            return
        self._content_title.set_title("HypeDevHome")
        self._content_title.set_subtitle(page.get_window_title())
        self._update_header_actions(page)

    def _update_header_actions(self, page: BasePage) -> None:
        """Update the header bar with page-specific action widgets."""
        # Clear existing actions
        while True:
            child = self._header_actions_box.get_first_child()
            if not child:
                break
            self._header_actions_box.remove(child)

        # Add new actions
        actions = page.get_header_actions()
        for action in actions:
            self._header_actions_box.append(action)

        if actions:
            log.debug("Updated header actions for page: %s", page.page_title)

    def _on_sidebar_row_selected(
        self,
        _listbox: Gtk.ListBox,
        row: Gtk.ListBoxRow | None,
    ) -> None:
        if row is None:
            return
        page_id = row.get_name()
        if page_id and page_id != self._current_page_id:
            self.navigate_to(page_id)

    # ── Keyboard shortcuts ──────────────────────────────

    def _setup_keyboard_shortcuts(self) -> None:
        """Register application-level keyboard shortcuts."""
        app = self.get_application()
        if not app:
            return

        shortcuts = [
            ("<Control>1", "nav-welcome", lambda: self.navigate_to("welcome")),
            ("<Control>2", "nav-system", lambda: self.navigate_to("system")),
            ("<Control>3", "nav-workstation", lambda: self.navigate_to("workstation")),
            ("<Control>4", "nav-dashboard", lambda: self.navigate_to("dashboard")),
            ("<Control>5", "nav-setup", lambda: self.navigate_to("machine-setup")),
            ("<Control>6", "nav-maintenance", lambda: self.navigate_to("maintenance")),
            ("<Control>7", "nav-extensions", lambda: self.navigate_to("extensions")),
            ("<Control>8", "nav-utilities", lambda: self.navigate_to("utilities")),
            ("F11", "toggle-fullscreen", self._toggle_fullscreen),
        ]

        for accel, name, callback in shortcuts:
            action = Gio.SimpleAction(name=name)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            app.add_action(action)
            app.set_accels_for_action(f"app.{name}", [accel])

        # Ctrl+, → settings
        app.set_accels_for_action("app.settings", ["<Control>comma"])

        # Shortcuts window
        shortcut_action = Gio.SimpleAction(name="show-shortcuts")
        shortcut_action.connect("activate", self._show_shortcuts_window)
        app.add_action(shortcut_action)
        app.set_accels_for_action("app.show-shortcuts", ["<Control>question"])

        # About action
        about_action = Gio.SimpleAction(name="about")
        about_action.connect("activate", self._show_about_dialog)
        app.add_action(about_action)

        # Settings action placeholder (real action in app.py)
        if not app.lookup_action("settings"):
            prefs_action = Gio.SimpleAction(name="settings")
            prefs_action.connect(
                "activate",
                self._show_preferences,
            )
            app.add_action(prefs_action)

        log.debug("Keyboard shortcuts registered")

    def _toggle_fullscreen(self) -> None:
        if self.is_fullscreen():
            self.unfullscreen()
        else:
            self.fullscreen()

    def _show_shortcuts_window(self, _action: Any, _param: Any) -> None:
        """Display the keyboard shortcuts overlay."""
        shortcuts = Gtk.ShortcutsWindow(transient_for=self, modal=True)

        section = Gtk.ShortcutsSection(title="Application", section_name="app")
        section.set_visible(True)

        nav_group = Gtk.ShortcutsGroup(title="Navigation")
        nav_group.set_visible(True)
        for key, desc in [
            ("<Control>1", "Go to Welcome"),
            ("<Control>2", "Go to System Monitor"),
            ("<Control>3", "Go to Tools"),
            ("<Control>4", "Go to Widgets"),
            ("<Control>5", "Go to Machine Setup"),
            ("<Control>6", "Go to Maintenance Hub"),
            ("<Control>7", "Go to Extensions"),
            ("<Control>8", "Go to Utilities"),
            ("Escape", "Back (nested page or show sidebar)"),
            ("F11", "Toggle Fullscreen"),
        ]:
            sc = Gtk.ShortcutsShortcut(
                accelerator=key,
                title=desc,
            )
            sc.set_visible(True)
            nav_group.append(sc)

        app_group = Gtk.ShortcutsGroup(title="Application")
        app_group.set_visible(True)
        for key, desc in [
            ("<Control>comma", "Settings"),
            ("<Control>q", "Quit (with confirmation if enabled)"),
            ("<Control>w", "Quit (with confirmation if enabled)"),
            ("<Control>question", "Keyboard Shortcuts"),
        ]:
            sc = Gtk.ShortcutsShortcut(accelerator=key, title=desc)
            sc.set_visible(True)
            app_group.append(sc)

        section.append(nav_group)
        section.append(app_group)
        shortcuts.add_section(section)
        shortcuts.present()

    def _show_preferences(self, _action: Any, _param: Any) -> None:
        """Display the Settings/Preferences dialog."""
        if not self.config:
            log.error("Config not available for settings")
            return

        dialog = SettingsDialog(self.config, transient_for=self)
        dialog.present()

    def _show_about_dialog(self, _action: Any, _param: Any) -> None:
        """Display the application About dialog."""
        if not self.config:
            log.error("Config not available for about dialog")
            return

        about = AboutDialog(self.config, transient_for=self)
        about.show()

    # ── Window lifecycle ────────────────────────────────

    def _on_close_request(self, _window: Adw.ApplicationWindow) -> bool:
        """Persist window dimensions; optionally confirm before closing."""
        if self._allow_close_without_confirm:
            self._allow_close_without_confirm = False
            w = self.get_width()
            h = self.get_height()
            if self.config:
                self.config.set("window_width", w)
                self.config.set("window_height", h)
                log.debug("Saved window size %dx%d", w, h)
            return False

        if not self.config or not self.config.get("confirm_quit", True):
            w = self.get_width()
            h = self.get_height()
            if self.config:
                self.config.set("window_width", w)
                self.config.set("window_height", h)
                log.debug("Saved window size %dx%d", w, h)
            return False

        dialog = Adw.MessageDialog(
            transient_for=self,
            heading="Quit HypeDevHome?",
            body="You can disable this confirmation under Settings → Behavior.",
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("quit", "Quit")
        dialog.set_response_appearance("quit", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")

        def on_response(dlg: Adw.MessageDialog, response: str) -> None:
            dlg.destroy()
            if response == "quit":
                self._allow_close_without_confirm = True
                self.close()

        dialog.connect("response", on_response)
        dialog.present()
        return True
