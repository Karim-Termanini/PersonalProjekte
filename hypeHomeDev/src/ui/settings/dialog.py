"""HypeDevHome — Settings dialog and panel."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gdk, Gtk  # noqa: E402

if TYPE_CHECKING:
    from config.manager import ConfigManager

log = logging.getLogger(__name__)


class SettingsDialog(Adw.PreferencesDialog):
    """Settings dialog for HypeDevHome."""

    def __init__(self, config_manager: ConfigManager, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(**kwargs)
        self.config = config_manager

        # Initialize auto-start manager
        from config.autostart import AutoStartManager

        self.auto_start_manager = AutoStartManager(config_manager)

        # Create preference pages
        self._create_appearance_page()
        self._create_behavior_page()
        self._create_dashboard_page()
        self._create_github_page()
        self._create_about_page()

        log.debug("Settings dialog initialized")

    def _create_appearance_page(self) -> None:
        """Create the Appearance settings page."""
        page = Adw.PreferencesPage(title="Appearance", icon_name="applications-graphics-symbolic")

        # Theme selection
        theme_group = Adw.PreferencesGroup(title="Theme")

        # Theme row
        theme_row = Adw.ComboRow(
            title="Theme",
            subtitle="Choose your preferred color theme",
            model=Gtk.StringList.new(["System", "Light", "Dark"]),
        )

        # Set current theme
        current_theme = self.config.get("theme", "system").capitalize()
        theme_map = {"system": 0, "light": 1, "dark": 2}
        if current_theme.lower() in theme_map:
            theme_row.set_selected(theme_map[current_theme.lower()])

        # Connect signal
        theme_row.connect("notify::selected", self._on_theme_changed)
        theme_group.add(theme_row)

        # Accent color (placeholder for future)
        accent_group = Adw.PreferencesGroup(title="Colors")
        accent_row = Adw.ActionRow(
            title="Accent Color", subtitle="Choose your accent color (coming soon)"
        )
        accent_group.add(accent_row)

        # Font size (placeholder for future)
        font_group = Adw.PreferencesGroup(title="Typography")
        font_row = Adw.ActionRow(title="Font Size", subtitle="Adjust font size (coming soon)")
        font_group.add(font_row)

        page.add(theme_group)
        page.add(accent_group)
        page.add(font_group)
        self.add(page)

    def _create_behavior_page(self) -> None:
        """Create the Behavior settings page."""
        page = Adw.PreferencesPage(title="Behavior", icon_name="preferences-system-symbolic")

        # Startup behavior
        startup_group = Adw.PreferencesGroup(title="Startup")

        # Auto-start row
        auto_start_row = Adw.SwitchRow(
            title="Start automatically on login", subtitle="Launch HypeDevHome when you log in"
        )
        auto_start_row.set_active(self.config.get("auto_start", False))
        auto_start_row.connect("notify::active", self._on_auto_start_changed)
        startup_group.add(auto_start_row)

        default_page_group = Adw.PreferencesGroup(title="Navigation")
        default_page_row = Adw.ActionRow(
            title="Startup page",
            subtitle="The last page you used is restored on launch. "
            "If no page was saved yet, Welcome opens first.",
        )
        default_page_group.add(default_page_row)

        # Confirmation dialogs
        confirm_group = Adw.PreferencesGroup(title="Confirmations")
        confirm_row = Adw.SwitchRow(
            title="Confirm before quitting",
            subtitle="Show a confirmation dialog when closing the application",
        )
        confirm_row.set_active(self.config.get("confirm_quit", True))
        confirm_row.connect("notify::active", self._on_confirm_quit_changed)
        confirm_group.add(confirm_row)

        page.add(startup_group)
        page.add(default_page_group)
        page.add(confirm_group)
        self.add(page)

    def _create_dashboard_page(self) -> None:
        """Create the Widgets (grid) settings page."""
        page = Adw.PreferencesPage(title="Widgets", icon_name="view-grid-symbolic")

        # Refresh settings
        refresh_group = Adw.PreferencesGroup(title="Refresh")

        # Refresh interval
        refresh_row = Adw.SpinRow(
            title="Refresh Interval",
            subtitle="How often to update dashboard widgets (seconds)",
            adjustment=Gtk.Adjustment(
                value=self.config.get("refresh_interval", 2.0),
                lower=1.0,
                upper=60.0,
                step_increment=1.0,
                page_increment=5.0,
            ),
        )
        refresh_row.connect("notify::value", self._on_refresh_interval_changed)
        refresh_group.add(refresh_row)

        # Animation preferences (placeholder)
        animation_group = Adw.PreferencesGroup(title="Animations")
        animation_row = Adw.SwitchRow(
            title="Enable animations", subtitle="Smooth transitions and effects"
        )
        animation_row.set_active(self.config.get("animations_enabled", True))
        animation_row.connect("notify::active", self._on_animations_changed)
        animation_group.add(animation_row)

        page.add(refresh_group)
        page.add(animation_group)
        self.add(page)

    def _create_github_page(self) -> None:
        """Create the GitHub integration settings page."""
        # Use the new GitHubSettingsPage
        from ui.settings.github import GitHubSettingsPage

        github_page = GitHubSettingsPage(self.config)
        self.add(github_page)

    def _create_about_page(self) -> None:
        """Create the About page."""
        page = Adw.PreferencesPage(title="About", icon_name="help-about-symbolic")

        # About group
        about_group = Adw.PreferencesGroup(title="HypeDevHome")

        # Version row
        try:
            import importlib.metadata

            version = importlib.metadata.version("hypedevhome")
        except (importlib.metadata.PackageNotFoundError, ImportError):
            version = "0.1.0"

        version_row = Adw.ActionRow(title="Version", subtitle=version)
        about_group.add(version_row)

        # License row
        license_row = Adw.ActionRow(
            title="License", subtitle="GNU General Public License v3.0 or later"
        )
        about_group.add(license_row)

        # Links group
        links_group = Adw.PreferencesGroup(title="Links")

        # GitHub row
        github_row = Adw.ActionRow(
            title="GitHub Repository", subtitle="View source code and report issues"
        )
        github_button = Gtk.Button(label="Open", valign=Gtk.Align.CENTER)
        github_button.connect("clicked", self._on_open_github)
        github_row.add_suffix(github_button)
        links_group.add(github_row)

        # Documentation row (placeholder)
        docs_row = Adw.ActionRow(
            title="Documentation", subtitle="Read the user guide and API documentation"
        )
        links_group.add(docs_row)

        page.add(about_group)
        page.add(links_group)
        self.add(page)

    # ── Signal handlers ─────────────────────────────────

    def _on_theme_changed(self, combo_row: Adw.ComboRow, _param: None) -> None:
        """Handle theme selection change."""
        theme_map = {0: "system", 1: "light", 2: "dark"}
        selected = combo_row.get_selected()
        if selected in theme_map:
            theme = theme_map[selected]
            self.config.set("theme", theme)
            log.info("Theme changed to: %s", theme)

            # Emit event to notify theme change
            from core.state import AppState

            bus = AppState.get().event_bus
            if bus:
                bus.emit("theme_changed", theme=theme)

    def _on_auto_start_changed(self, switch_row: Adw.SwitchRow, _param: None) -> None:
        """Handle auto-start toggle change."""
        auto_start = switch_row.get_active()

        if auto_start:
            success = self.auto_start_manager.enable()
        else:
            success = self.auto_start_manager.disable()

        if success:
            self.config.set("auto_start", auto_start)
            log.info("Auto-start changed to: %s", auto_start)
        else:
            # Revert the switch if operation failed
            switch_row.set_active(not auto_start)
            log.error("Failed to change auto-start setting")

    def _on_confirm_quit_changed(self, switch_row: Adw.SwitchRow, _param: None) -> None:
        """Handle confirm quit toggle change."""
        confirm_quit = switch_row.get_active()
        self.config.set("confirm_quit", confirm_quit)
        log.info("Confirm quit changed to: %s", confirm_quit)

    def _on_refresh_interval_changed(self, spin_row: Adw.SpinRow, _param: None) -> None:
        """Handle refresh interval change."""
        interval = spin_row.get_value()
        self.config.set("refresh_interval", interval)
        log.info("Refresh interval changed to: %s seconds", interval)

        # Emit event to notify refresh interval change
        from core.state import AppState

        bus = AppState.get().event_bus
        if bus:
            bus.emit("config.refresh-interval-changed", interval=interval)

    def _on_animations_changed(self, switch_row: Adw.SwitchRow, _param: None) -> None:
        """Handle animations toggle change."""
        animations_enabled = switch_row.get_active()
        self.config.set("animations_enabled", animations_enabled)
        log.info("Animations changed to: %s", animations_enabled)

    def _on_open_github(self, _button: Gtk.Button) -> None:
        """Open GitHub repository in default browser."""
        uri = "https://github.com/hypedevhome/hypeHomeDev"
        try:
            Gtk.show_uri(None, uri, Gdk.CURRENT_TIME)
        except (AttributeError, ImportError):
            # Fallback for environments without Gdk
            import webbrowser

            webbrowser.open(uri)
        log.info("Opening GitHub repository: %s", uri)
