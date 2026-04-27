"""HypeDevHome — Workstation hub (Phase 7).

Sidebar: Hub, Apps, Servers, Services, AI, Config, Install, Remove. Learn content lives on Welcome, Servers, Install, and Config.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk  # noqa: E402

from ui.pages.base_page import BasePage  # noqa: E402
from ui.widgets.workstation import (  # noqa: E402
    WorkstationAIPanel,
    WorkstationAppsPanel,
    WorkstationConfigPanel,
    WorkstationInstallPanel,
    WorkstationRemovePanel,
    WorkstationServersPanel,
    WorkstationServicesPanel,
)

log = logging.getLogger(__name__)

# Each entry: (page_id | None for separator, title, subtitle, icon_name, group_header)
# page_id=None → renders a non-selectable section label
_SIDEBAR_ITEMS: tuple[tuple[str | None, str, str, str], ...] = (
    # ── EXPLORE ────────────────────────────────────────────────────
    (None, "EXPLORE", "", ""),
    (
        "apps",
        "Installed Apps",
        "Browse, search and configure installed applications",
        "view-app-grid-symbolic",
    ),
    (
        "servers",
        "Servers & Docker",
        "Docker containers, ports, systemd — live system overview",
        "network-server-symbolic",
    ),
    (
        "services",
        "Services",
        "Tailscale, NordVPN, Bitwarden, Dropbox, 1Password",
        "application-x-firmware-symbolic",
    ),
    (
        "ai",
        "AI & Models",
        "Ollama, LM Studio, Open WebUI, GitHub Copilot CLI",
        "preferences-desktop-accessibility-symbolic",
    ),
    # ── MANAGE ─────────────────────────────────────────────────────
    (None, "MANAGE", "", ""),
    (
        "config",
        "Git & SSH Config",
        "Git identity, SSH keys, dotfiles, Bash aliases",
        "emblem-synchronizing-symbolic",
    ),
    (
        "install",
        "Install Packages",
        "Languages, editors, terminals — includes Machine Setup wizard",
        "folder-download-symbolic",
    ),
    (
        "remove",
        "Uninstall",
        "Safely remove packages and development stacks",
        "edit-delete-symbolic",
    ),
    # ── PLATFORM ───────────────────────────────────────────────────
    (None, "PLATFORM", "", ""),
    (
        "extensions",
        "Extensions",
        "Browse and install extensions to add new features",
        "application-x-addon-symbolic",
    ),
)


class WorkstationPage(BasePage):
    """Tools hub: Apps, Servers, Services, AI, Config, Install, Remove, Extensions."""

    page_title = "Tools"
    page_icon = "preferences-desktop-apps-symbolic"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Default to Apps (first real section)
        self._current_view = "apps"
        self._view_titles: dict[str, str] = {
            key: title for key, title, _s, _i in _SIDEBAR_ITEMS if key is not None
        }
        self._subsection_reset_widgets: list[Any] = []
        self._stack_pages: dict[str, Gtk.Widget] = {}

    def build_content(self) -> None:
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.set_hexpand(True)
        outer.set_vexpand(True)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        body.set_hexpand(True)
        body.set_vexpand(True)

        # ── Sidebar (section list) ─────────────────────────────
        self._sidebar = Gtk.ListBox(
            selection_mode=Gtk.SelectionMode.SINGLE,
            css_classes=["navigation-sidebar"],
        )
        self._sidebar.set_size_request(240, -1)
        self._sidebar.connect("row-selected", self._on_sidebar_row_selected)

        for page_id, title, subtitle, icon_name in _SIDEBAR_ITEMS:
            if page_id is None:
                # Non-selectable category header
                header = self._make_sidebar_header(title)
                self._sidebar.append(header)
            else:
                row = self._make_sidebar_row(page_id, title, subtitle, icon_name)
                self._sidebar.append(row)

        sidebar_scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        sidebar_scroll.set_child(self._sidebar)

        sep = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)

        # ── Content stack ─────────────────────────────────────
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
            hexpand=True,
            vexpand=True,
        )

        apps_p = WorkstationAppsPanel()
        servers_p = WorkstationServersPanel()
        services_p = WorkstationServicesPanel()
        ai_p = WorkstationAIPanel()
        config_p = WorkstationConfigPanel()
        install_p = WorkstationInstallPanel()
        remove_p = WorkstationRemovePanel()
        extensions_p = self._build_extensions_placeholder()
        self._subsection_reset_widgets = [
            apps_p, servers_p, services_p, ai_p, config_p, install_p, remove_p,
        ]
        self._stack_pages = {
            "apps": apps_p,
            "servers": servers_p,
            "services": services_p,
            "ai": ai_p,
            "config": config_p,
            "install": install_p,
            "remove": remove_p,
            "extensions": extensions_p,
        }

        self._stack.add_named(apps_p, "apps")
        self._stack.add_named(servers_p, "servers")
        self._stack.add_named(services_p, "services")
        self._stack.add_named(ai_p, "ai")
        self._stack.add_named(config_p, "config")
        self._stack.add_named(install_p, "install")
        self._stack.add_named(remove_p, "remove")
        self._stack.add_named(extensions_p, "extensions")

        body.append(sidebar_scroll)
        body.append(sep)
        body.append(self._stack)
        outer.append(body)

        self.append(outer)

        self._goto_workstation_section(self._current_view)

    def _build_extensions_placeholder(self) -> Gtk.Widget:
        """Extensions placeholder — Phase 6 will fill this."""
        import gi as _gi
        _gi.require_version("Adw", "1")
        from gi.repository import Adw
        status = Adw.StatusPage(
            title="Extensions",
            description="Browse and manage extensions to add new features.\nComing in Phase 6.",
            icon_name="application-x-addon-symbolic",
            vexpand=True,
        )
        return status

    def _make_sidebar_header(self, title: str) -> "Gtk.ListBoxRow":
        """Non-selectable group label divider."""
        lbl = Gtk.Label(label=title)
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_start(14)
        lbl.set_margin_top(14)
        lbl.set_margin_bottom(2)
        lbl.add_css_class("sidebar-group-header")
        row = Gtk.ListBoxRow(child=lbl)
        row.set_selectable(False)
        row.set_activatable(False)
        row.set_name("__header__")
        return row

    def _make_sidebar_row(
        self, page_id: str, title: str, subtitle: str, icon_name: str
    ) -> Gtk.ListBoxRow:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_valign(Gtk.Align.CENTER)

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_col.set_hexpand(True)
        title_lbl = Gtk.Label(label=title, xalign=0.0)
        title_lbl.add_css_class("heading")
        sub_lbl = Gtk.Label(label=subtitle, xalign=0.0)
        sub_lbl.add_css_class("caption")
        sub_lbl.add_css_class("dim-label")
        sub_lbl.set_wrap(True)
        sub_lbl.set_natural_wrap_mode(True)
        text_col.append(title_lbl)
        text_col.append(sub_lbl)

        box.append(icon)
        box.append(text_col)

        row = Gtk.ListBoxRow(child=box)
        row.set_name(page_id)
        return row

    def _on_sidebar_row_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        page_id = row.get_name()
        if page_id:
            self._show_section(page_id)

    def _show_section(self, page_id: str) -> None:
        if page_id not in self._view_titles:
            log.warning("WorkstationPage: unknown section %s", page_id)
            return
        self._current_view = page_id
        self._stack.set_visible_child_name(page_id)
        self._sync_window_header()

    def goto_section(self, page_id: str) -> bool:
        """Public API: switch to a Workstation sidebar subsection (``apps``, ``servers``, …)."""
        # 1. Check if it's a top-level sidebar section
        if page_id in self._stack_pages:
            self._goto_workstation_section(page_id)
            return True

        # 2. Deep-link into the Config hub (config:git, config:ssh, …)
        if page_id.startswith("config:"):
            inner = page_id[7:]
            config = self._stack_pages.get("config")
            go_sub = getattr(config, "goto_subsection", None)
            if config and callable(go_sub) and go_sub(inner):
                self._goto_workstation_section("config")
                return True

        # 3. Deep-link into the Remove hub (remove:cleanup, remove:alacritty, …)
        if page_id.startswith("remove:"):
            inner = page_id[7:]
            remove = self._stack_pages.get("remove")
            go_sub = getattr(remove, "goto_subsection", None)
            if remove and callable(go_sub) and go_sub(inner):
                self._goto_workstation_section("remove")
                return True

        # 3b. Deep-link into the Servers hub (servers:docker, servers:overview, …)
        if page_id.startswith("servers:"):
            inner = page_id[8:]
            servers = self._stack_pages.get("servers")
            go_sub = getattr(servers, "goto_subsection", None)
            if servers and callable(go_sub) and go_sub(inner):
                self._goto_workstation_section("servers")
                return True

        # 4. Deep-link into the Install hub
        install = self._stack_pages.get("install")
        if install:
            # Check if this ID is something the install panel can handle
            go_sub = getattr(install, "goto_subsection", None)
            if callable(go_sub) and go_sub(page_id):
                self._goto_workstation_section("install")
                return True

        log.warning("WorkstationPage: unknown subsection %r", page_id)
        return False

    def _goto_workstation_section(self, page_id: str) -> None:
        """Switch stack and sidebar to another Workstation subsection (e.g. from Config)."""
        self._show_section(page_id)
        # Note: We don't reset subsections here if we are doing a precision deep-link
        # but the caller of _show_section is usually goto_section.
        i = 0
        while True:
            row = self._sidebar.get_row_at_index(i)
            if row is None:
                break
            if row.get_name() == page_id:
                self._sidebar.select_row(row)
                break
            i += 1

    def _sync_window_header(self) -> None:
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
        section = self._view_titles.get(self._current_view, "")
        if section:
            return f"{self.page_title} — {section}"
        return self.page_title

    def show_sidebar_toggle_in_header(self) -> bool:
        return True

    def get_header_actions(self) -> list[Gtk.Widget]:
        return []

    def handle_escape(self) -> bool:
        return False

    def on_hidden(self) -> None:
        super().on_hidden()
        for w in self._subsection_reset_widgets:
            reset = getattr(w, "reset_subsections", None)
            if callable(reset):
                reset()
        self._current_view = "apps"

        def _restore(_a: Any = None) -> bool:
            if self._sidebar.get_first_child():
                self._goto_workstation_section("apps")
            return False

        GLib.idle_add(_restore)
