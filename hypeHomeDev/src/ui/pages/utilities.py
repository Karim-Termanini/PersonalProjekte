"""HypeDevHome - Utilities page.

The Utilities page serves as a hub for various developer tools:
 - Hosts file editor
 - Environment variables manager
 - Desktop configuration
 - System 'Pulse' maintenance widgets
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from typing import Any, cast

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.maintenance.pulse_manager import PulseManager  # noqa: E402
from core.state import AppState  # noqa: E402
from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.desktop_config import DesktopConfig  # noqa: E402
from ui.widgets.env_editor import EnvEditor  # noqa: E402
from ui.widgets.hosts_editor import HostsEditor  # noqa: E402
from ui.widgets.pulse_dashboard import PulseDashboard  # noqa: E402
from ui.widgets.utilities_environments import UtilitiesEnvironments  # noqa: E402
from ui.widgets.utilities_system_info import UtilitiesSystemInfo  # noqa: E402

log = logging.getLogger(__name__)


class UtilitiesPage(BasePage):
    """Developer utility tools hub."""

    page_title = "Utilities"
    page_icon = "applications-utilities-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_view = "hub"
        state = AppState.get()
        self._pulse_manager = state.pulse_manager
        if not self._pulse_manager:
            from core.setup.host_executor import HostExecutor

            self._pulse_manager = PulseManager(HostExecutor())
            state.pulse_manager = self._pulse_manager

        self._pulse_status_label: Gtk.Label | None = None
        self._detection_label: Gtk.Label | None = None
        self._hub_timer_id = 0
        # Sub-view titles for the main window header (avoid a second in-page HeaderBar).
        self._view_titles: dict[str, str] = {
            "hub": self.page_title,
            "hosts": "Hosts Editor",
            "env": "Environment Variables",
            "desktop": "Desktop Configuration",
            "pulse": "System Pulse",
            "sysinfo": "System Information",
            "environments": "Environments",
        }

    def on_shown(self) -> None:
        super().on_shown()
        if self._hub_timer_id == 0:
            self._hub_timer_id = GLib.timeout_add_seconds(10, self._refresh_hub_status)

    def build_content(self) -> None:
        """Build the utilities hub and sub-pages."""
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=300,
        )

        # 1. Hub View
        self._hub_view = self._build_hub_view()
        self._stack.add_named(self._hub_view, "hub")

        # 2. Hosts Editor View
        self._hosts_view = self._build_tool_view(
            "hosts",
            HostsEditor(),
            description=(
                "Maps names to IP addresses in /etc/hosts (system DNS before DNS). "
                "Comment lines and blank lines are ignored in the list. "
                "Saving changes may ask for your password (pkexec) because the file is system-owned."
            ),
        )
        self._stack.add_named(self._hosts_view, "hosts")

        # 3. Env Vars Editor View
        self._env_view = self._build_tool_view(
            "env",
            EnvEditor(),
            description=(
                "User and system variables (PATH, tokens, editors, …). "
                "What you see comes from your profile files and system defaults — "
                "edit here, then open a new terminal so shells pick up changes where needed."
            ),
        )
        self._stack.add_named(self._env_view, "env")

        # 4. Desktop Config View
        self._desktop_view = self._build_tool_view(
            "desktop",
            DesktopConfig(),
            description=(
                "Theme, font scaling, animations, and tiling-related toggles for GNOME-style sessions. "
                "Not every option applies to every desktop; some need a logout to take effect."
            ),
        )
        self._stack.add_named(self._desktop_view, "desktop")

        # 5. Pulse View
        self._pulse_view = self._build_tool_view(
            "pulse",
            PulseDashboard(),
            description=(
                "Maintenance snapshot style health: CPU/RAM, containers, and pending tasks. "
                "Uses the same Pulse engine as the Maintenance hub — "
                "good for a quick check without leaving Utilities."
            ),
        )
        self._stack.add_named(self._pulse_view, "pulse")

        self._sysinfo_view = self._build_tool_view(
            "sysinfo",
            UtilitiesSystemInfo(),
            description="OS release, kernel/platform, memory and disk snapshot from this process.",
        )
        self._stack.add_named(self._sysinfo_view, "sysinfo")

        self._env_view_util = self._build_tool_view(
            "environments",
            UtilitiesEnvironments(),
            description="Container tools (Docker, Podman, Distrobox, Toolbx). Full templates live in Machine Setup.",
        )
        self._stack.add_named(self._env_view_util, "environments")

        self.append(self._stack)

    def _build_hub_view(self) -> Gtk.Widget:
        """Build the main hub view with categories and action rows."""
        scroll = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER
        )
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_tightening_threshold(600)

        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            margin_top=32,
            margin_bottom=32,
        )

        # Add a centered header (PreferencesPage only accepts PreferencesGroup children)
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        header_box.set_margin_top(16)
        header_box.set_margin_bottom(8)
        header_box.set_halign(Gtk.Align.CENTER)

        icon = Gtk.Image.new_from_icon_name("applications-utilities-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")

        title_label = Gtk.Label(label="Developer Utilities")
        title_label.add_css_class("title-1")

        desc_label = Gtk.Label(
            label=(
                "Hosts, environment variables, desktop tweaks, and Pulse health — "
                "open a row to edit. Detection below is read-only reference from this process; "
                "sub-pages load live system data when you open them."
            )
        )
        desc_label.add_css_class("caption")
        desc_label.add_css_class("dim-label")
        desc_label.set_wrap(True)
        desc_label.set_justify(Gtk.Justification.CENTER)
        desc_label.set_max_width_chars(56)

        self._detection_label = Gtk.Label()
        self._detection_label.add_css_class("caption")
        self._detection_label.add_css_class("dim-label")
        self._detection_label.set_wrap(True)
        self._detection_label.set_justify(Gtk.Justification.CENTER)
        self._detection_label.set_max_width_chars(60)
        self._refresh_detection_label()

        header_box.append(icon)
        header_box.append(title_label)
        header_box.append(desc_label)
        header_box.append(self._detection_label)

        page.append(header_box)

        # --- Networking ---
        net_group = Adw.PreferencesGroup(
            title="Networking", description="Local DNS and host resolution"
        )

        hosts_row = Adw.ActionRow(
            title="Hosts Editor",
            subtitle="View and edit /etc/hosts entries securely",
            icon_name="network-server-symbolic",
            activatable=True,
        )
        hosts_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        hosts_row.connect("activated", lambda _: self.navigate_to("hosts"))
        net_group.add(hosts_row)
        page.append(net_group)

        # --- Environment ---
        env_group = Adw.PreferencesGroup(
            title="Environment", description="Manage shell and system variables"
        )

        env_row = Adw.ActionRow(
            title="Environment Variables",
            subtitle="Configure PATH, API keys, and other exports",
            icon_name="emblem-system-symbolic",
            activatable=True,
        )
        env_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        env_row.connect("activated", lambda _: self.navigate_to("env"))
        env_group.add(env_row)
        page.append(env_group)

        # --- System Settings ---
        sys_group = Adw.PreferencesGroup(
            title="Desktop Configuration", description="Personalize your development desktop"
        )

        desktop_row = Adw.ActionRow(
            title="Desktop Config",
            subtitle="GNOME, KDE, and Tiling settings",
            icon_name="preferences-desktop-display-symbolic",
            activatable=True,
        )
        desktop_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        desktop_row.connect("activated", lambda _: self.navigate_to("desktop"))
        sys_group.add(desktop_row)
        page.append(sys_group)

        # --- Maintenance Pulse ---
        pulse_group = Adw.PreferencesGroup(
            title="Maintenance Pulse", description="Real-time system health and optimization"
        )

        # We'll put a simplified status here or a row that leads to a dashboard
        pulse_row = Adw.ActionRow(
            title="System Pulse",
            subtitle="Check maintenance status and pending tasks",
            icon_name="utilities-system-monitor-symbolic",
            activatable=True,
        )
        # Pulse status indicator suffix
        status_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self._pulse_status_label = Gtk.Label(label="Healthy")
        self._pulse_status_label.add_css_class("success")
        status_box.append(self._pulse_status_label)
        pulse_row.add_suffix(status_box)
        pulse_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        pulse_row.connect("activated", lambda _: self.navigate_to("pulse"))

        pulse_group.add(pulse_row)
        page.append(pulse_group)

        more_group = Adw.PreferencesGroup(
            title="More tools", description="Phase 5 utilities — system info and environments"
        )
        sys_row = Adw.ActionRow(
            title="System information",
            subtitle="OS, kernel, memory, and disk usage",
            icon_name="computer-symbolic",
            activatable=True,
        )
        sys_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        sys_row.connect("activated", lambda _: self.navigate_to("sysinfo"))
        more_group.add(sys_row)

        env_row = Adw.ActionRow(
            title="Environments",
            subtitle="Docker, Podman, Distrobox detection — use Machine Setup for full setup",
            icon_name="applications-engineering-symbolic",
            activatable=True,
        )
        env_row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        env_row.connect("activated", lambda _: self.navigate_to("environments"))
        more_group.add(env_row)
        page.append(more_group)

        clamp.set_child(page)
        scroll.set_child(clamp)
        return scroll

    def _refresh_detection_label(self) -> None:
        """Show Python/shell paths for context (informational)."""
        if not self._detection_label:
            return
        lines = [
            f"Python {sys.version.split()[0]} — {sys.executable}",
        ]
        p3 = shutil.which("python3")
        if p3 and os.path.normpath(p3) != os.path.normpath(sys.executable):
            lines.append(f"python3 on PATH: {p3}")
        if shell := os.environ.get("SHELL"):
            lines.append(f"SHELL: {shell}")
        self._detection_label.set_label("Detected: " + " · ".join(lines))

    def _refresh_hub_status(self) -> bool:
        """Update status indicators on the hub view."""
        if not self._pulse_manager or not self._pulse_status_label:
            return True

        summary = self._pulse_manager.get_summary()
        self._pulse_status_label.set_label(summary["status"])

        # Color coding
        self._pulse_status_label.remove_css_class("success")
        self._pulse_status_label.remove_css_class("warning")
        if summary["status"] == "Healthy":
            self._pulse_status_label.add_css_class("success")
        else:
            self._pulse_status_label.add_css_class("warning")

        return True

    def _build_tool_view(
        self,
        view_key: str,
        tool_widget: Gtk.Widget,
        *,
        description: str = "",
    ) -> Gtk.Widget:
        """Create a full-page view for a specific tool.

        Window title uses :attr:`_view_titles` ``[view_key]``; back uses the main header.
        """
        assert view_key in self._view_titles, view_key
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        if description:
            blurb = Gtk.Label(label=description)
            blurb.set_wrap(True)
            blurb.set_xalign(0)
            blurb.add_css_class("dim-label")
            blurb.set_margin_start(16)
            blurb.set_margin_end(16)
            blurb.set_margin_top(10)
            blurb.set_margin_bottom(6)
            box.append(blurb)

        box.append(tool_widget)
        return box

    def navigate_to(self, view_name: str) -> None:
        """Navigate to a specific view in the stack."""
        self._current_view = view_name
        self._stack.set_visible_child_name(view_name)
        self._sync_window_header()
        log.debug("UtilitiesPage navigated to: %s", view_name)

    def _sync_window_header(self) -> None:
        """Update main window title + actions when drilling into a tool or back to hub."""
        app = Gtk.Application.get_default()
        if not app:
            return
        win = cast(Gtk.Application, app).get_active_window()
        if win is None:
            return
        refresh = getattr(win, "refresh_current_page_header", None)
        if callable(refresh):
            refresh()

    def get_window_title(self) -> str:
        return self._view_titles.get(self._current_view, self.page_title)

    def show_sidebar_toggle_in_header(self) -> bool:
        """Hide sidebar control while drilled into a tool — same icon as back was duplicated."""
        return self._current_view == "hub"

    def get_header_actions(self) -> list[Gtk.Widget]:
        """Back control lives in the main header next to the sidebar toggle."""
        if self._current_view == "hub":
            return []
        back_btn = Gtk.Button(icon_name="go-previous-symbolic")
        back_btn.set_tooltip_text("Back to Utilities")
        back_btn.connect("clicked", lambda _b: self.navigate_to("hub"))
        return [back_btn]

    def handle_escape(self) -> bool:
        """Escape returns from a tool view to the utilities hub."""
        self.ensure_built()
        if self._current_view != "hub":
            self.navigate_to("hub")
            return True
        return False

    def on_hidden(self) -> None:
        """Reset to hub view when navigating away."""
        super().on_hidden()
        self.navigate_to("hub")

        if self._hub_timer_id:
            GLib.source_remove(self._hub_timer_id)
            self._hub_timer_id = 0

    def __del__(self) -> None:
        if self._hub_timer_id:
            import contextlib

            with contextlib.suppress(Exception):
                GLib.source_remove(self._hub_timer_id)
            self._hub_timer_id = 0
