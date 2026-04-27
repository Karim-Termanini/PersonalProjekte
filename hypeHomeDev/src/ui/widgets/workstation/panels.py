"""Workstation hub — Config, Install, Remove (subsection bar per area); Learn content moved contextually."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any, Literal

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402, I001

from core.setup.distro_detector import DistroDetector  # noqa: E402
from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.package_installer import PackageInstaller  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.backend_issues_page import BackendIssuesPage  # noqa: E402
from ui.widgets.workstation.desktop_cli_reference_page import DesktopCliReferencePage  # noqa: E402
from ui.widgets.workstation.install_catalog import (  # noqa: E402
    build_row_command,
    catalog_groups,
    category_from_catalog,
)
from ui.widgets.workstation.nav_helper import (  # noqa: E402
    copy_plain_text_to_clipboard,
    navigate_main_window,
    navigate_workstation_section,
)
from ui.widgets.workstation.nvim_cheatsheet import NeovimCheatsheetPage  # noqa: E402
from ui.widgets.workstation.session_info import desktop_session_lines  # noqa: E402
from ui.widgets.workstation.subsection_bar import WorkstationSubsectionBar  # noqa: E402
from ui.widgets.workstation.workstation_learning_scroll import (  # noqa: E402
    schedule_scroll_widget_into_view,
)
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    PACKAGE_MANAGER as _PKG_MANAGER,
    _add_runnable_row,
    _add_terminal_row,
)

log = logging.getLogger(__name__)

_PRELOAD_LIMIT = 5000


def _copy_cmd(cmd: str) -> None:
    if copy_plain_text_to_clipboard(cmd):
        emit_utility_toast("Command copied.", "info", timeout=4)
    else:
        emit_utility_toast("Could not copy to clipboard.", "error")


def _add_copy_rows(
    group: Adw.PreferencesGroup,
    rows: list[tuple[str, str]],
) -> None:
    for title, cmd in rows:
        _add_one_copy_row(group, title, cmd)


def _add_one_copy_row(group: Adw.PreferencesGroup, title: str, cmd: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=cmd)
        btn = Gtk.Button(label="Copy")
        btn.connect("clicked", lambda _b, c=cmd: _copy_cmd(c))
        row.add_suffix(btn)
        group.add(row)


def _page_one_group(title: str, description: str) -> Adw.PreferencesPage:
    p = Adw.PreferencesPage()
    p.add(Adw.PreferencesGroup(title=title, description=description))
    return p


def build_session_keybindings_page() -> Adw.PreferencesPage:
    """Desktop session + keybindings (formerly Learn → Session)."""
    return _page_one_group(
        "System keybindings",
        (
            "Read-only, environment-aware reference. "
            "Adjust shortcuts in your desktop or compositor settings.\n\n"
            f"{desktop_session_lines()}"
        ),
    )


_install_page_instance: WorkstationInstallPackagesPage | None = None


class WorkstationInstallPackagesPage(Gtk.Box):
    """Interactive package picker for distro manager + flatpak."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        global _install_page_instance
        _install_page_instance = self
        self._installer = PackageInstaller(HostExecutor())
        self._detector = DistroDetector(HostExecutor())
        self._search_job = 0
        self._source_values: list[str] = []
        self._selected: dict[str, bool] = {}
        self._tooltip_cache: dict[str, str] = {}
        self._installed_ids: set[str] = set()
        self._base_results: list[tuple[str, str, str, str]] = []
        self._results: list[tuple[str, str, str, str]] = []
        self._install_row_progress: dict[str, Gtk.ProgressBar] = {}

        group = Adw.PreferencesGroup(
            title="Packages",
            description="Search package source, select many, install selected.",
        )
        self.append(group)

        self._source = Gtk.DropDown(model=Gtk.StringList.new(["loading..."]))
        self._source.connect("notify::selected", self._on_filters_changed)
        source_row = Adw.ActionRow(title="Source", subtitle="Distro manager or Flatpak")
        source_row.add_suffix(self._source)
        group.add(source_row)

        self._search = Gtk.SearchEntry(placeholder_text="Search packages...")
        self._search.connect("search-changed", self._on_filters_changed)
        search_row = Adw.ActionRow(title="Search", subtitle="Type package name")
        search_row.add_suffix(self._search)
        group.add(search_row)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_valign(Gtk.Align.CENTER)
        self._install_btn = Gtk.Button(label="Install selected")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.connect("clicked", self._on_install_selected)
        actions.append(self._install_btn)
        self._status = Gtk.Label(label="Loading package sources…", xalign=0.0)
        self._status.add_css_class("dim-label")
        actions.append(self._status)
        action_row = Adw.ActionRow(title="Action")
        action_row.add_suffix(actions)
        group.add(action_row)

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_min_content_height(300)
        scrolled.set_child(self._list)
        self.append(scrolled)

        GLib.idle_add(self._start_init)

    def _start_init(self) -> bool:
        self._run_task(self._load_sources(), "Could not start package source loading.")
        return False

    def _run_task(self, coro: Any, err_label: str) -> None:
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            app.enqueue_task(coro)  # type: ignore[attr-defined]
            return
        try:
            asyncio.get_event_loop().create_task(coro)
        except RuntimeError:
            self._status.set_label(err_label)

    async def _load_sources(self) -> None:
        try:
            init_ok = await asyncio.wait_for(self._installer.initialize(), timeout=20)
            if not init_ok:
                GLib.idle_add(self._status.set_label, "Failed to init package backends.")
                return
            info = await asyncio.wait_for(self._detector.detect(), timeout=10)
            values = (
                [info.package_manager]
                if info.package_manager and info.package_manager != "unknown"
                else []
            )
            if info.has_flatpak:
                values.append("flatpak")
            values = [v.lower() for v in values if v]
            if not values:
                GLib.idle_add(self._status.set_label, "No package source detected.")
                return
            GLib.idle_add(self._apply_sources, values)
        except TimeoutError:
            GLib.idle_add(self._status.set_label, "Package source detection timed out.")
        except Exception:
            log.exception("WorkstationInstallPackagesPage: load sources failed")
            GLib.idle_add(self._status.set_label, "Failed loading package sources.")

    def _apply_sources(self, values: list[str]) -> None:
        self._source_values = values
        self._source.set_model(Gtk.StringList.new(values))
        self._source.set_selected(0)
        source = self._get_source()
        if source:
            self._status.set_label(f"Loading {source} packages…")
            self._run_task(self._load_initial_packages(source), "Could not load package list.")
        else:
            self._status.set_label("No source selected.")

    def _on_filters_changed(self, *_args: Any) -> None:
        source = self._get_source()
        if not source:
            return
        # Source changed: reload base list first
        if not self._base_results or any(s != source for s, _, _, _ in self._base_results):
            self._status.set_label(f"Loading {source} packages…")
            self._run_task(self._load_initial_packages(source), "Could not load package list.")
            return
        query = (self._search.get_text() or "").strip().lower()
        if not query:
            self._set_results(self._base_results[:300])
            self._status.set_label(f"{len(self._base_results)} available in {source}.")
            return
        filtered = self._smart_filter_rows(query, self._base_results, limit=300)
        self._set_results(filtered)
        self._status.set_label(f"{len(filtered)} matched in {source}.")
        self._search_job += 1

    def _get_source(self) -> str:
        i = self._source.get_selected()
        if 0 <= i < len(self._source_values):
            return self._source_values[i]
        return ""

    async def _load_initial_packages(self, source: str) -> None:
        rows = await self._installer.list_packages_by_source(source, limit=_PRELOAD_LIMIT)
        installed_ids = await self._get_installed_ids(source)
        mapped = [(source, pkg_id, pkg_name, pkg_desc) for pkg_id, pkg_name, pkg_desc in rows]
        GLib.idle_add(self._apply_base_results, source, mapped, len(rows) >= _PRELOAD_LIMIT, installed_ids)

    async def _get_installed_ids(self, source: str) -> set[str]:
        """Installed package IDs as reported by the OS (normalized per source)."""
        source_key = source.strip().lower()
        ex = self._installer._executor
        try:
            if source_key == "flatpak":
                merged: set[str] = set()
                for cmd in (
                    ["flatpak", "list", "--app", "--columns=application", "--system"],
                    ["flatpak", "list", "--app", "--columns=application", "--user"],
                ):
                    res = await ex.run_async(cmd, timeout=45)
                    if res.success:
                        merged.update(ln.strip() for ln in res.stdout.splitlines() if ln.strip())
                if not merged:
                    res = await ex.run_async(
                        ["flatpak", "list", "--app", "--columns=application"], timeout=45
                    )
                    if res.success:
                        merged.update(ln.strip() for ln in res.stdout.splitlines() if ln.strip())
                return merged
            if source_key == "dnf":
                res = await ex.run_async(["rpm", "-qa", "--qf", "%{NAME}\\n"], timeout=60)
                if res.success:
                    return {ln.strip().lower() for ln in res.stdout.splitlines() if ln.strip()}
            if source_key == "apt":
                res = await ex.run_async(
                    ["dpkg-query", "-f", "${Package}\\n", "-W"], timeout=60
                )
                if res.success:
                    return {ln.strip().lower() for ln in res.stdout.splitlines() if ln.strip()}
            if source_key == "pacman":
                res = await ex.run_async(["pacman", "-Qq"], timeout=60)
                if res.success:
                    return {ln.strip() for ln in res.stdout.splitlines() if ln.strip()}
            if source_key == "zypper":
                res = await ex.run_async(["rpm", "-qa", "--qf", "%{NAME}\\n"], timeout=60)
                if res.success:
                    return {ln.strip().lower() for ln in res.stdout.splitlines() if ln.strip()}
        except Exception:
            log.exception("Failed to get installed IDs for %s", source)
        return set()

    def _is_pkg_installed(self, source: str, pkg_id: str) -> bool:
        sk = source.strip().lower()
        if sk in {"dnf", "apt", "zypper"}:
            return pkg_id.strip().lower() in self._installed_ids
        return pkg_id.strip() in self._installed_ids

    def _apply_base_results(
        self, source: str, rows: list[tuple[str, str, str, str]], capped: bool,
        installed_ids: set[str] | None = None,
    ) -> None:
        self._base_results = rows
        if installed_ids is not None:
            self._installed_ids = installed_ids
        self._set_results(rows[:300])
        if capped:
            self._status.set_label(
                f"Showing first {_PRELOAD_LIMIT} packages in {source}. Type to filter narrower."
            )
        else:
            self._status.set_label(f"{len(rows)} available in {source}. Type to filter.")

    def _smart_filter_rows(
        self, query: str, rows: list[tuple[str, str, str, str]], limit: int = 300
    ) -> list[tuple[str, str, str, str]]:
        q = self._norm(query)
        q_tokens = [t for t in q.split() if t]
        if not q_tokens:
            return rows[:limit]

        related = {
            "clock": ["time", "timer", "alarm", "watch", "calendar"],
            "browser": ["web", "internet", "firefox", "chrome"],
            "music": ["audio", "player", "sound"],
            "video": ["movie", "media", "player"],
            "admin": ["system", "settings", "control", "policy", "security", "manager", "network", "root"],
            "administrator": ["system", "settings", "control", "policy", "security", "manager", "network", "root"],
            "code": ["editor", "ide", "vscode", "visual", "programming", "development"],
            "editor": ["code", "text", "ide", "vim", "emacs", "nano"],
        }
        related_tokens: set[str] = set()
        for token in q_tokens:
            related_tokens.update(related.get(token, []))

        scored: list[tuple[int, tuple[str, str, str, str]]] = []
        for row in rows:
            _source, pkg_id, pkg_name, pkg_desc = row
            name_norm = self._norm(pkg_name)
            id_norm = self._norm(pkg_id)
            desc_norm = self._norm(pkg_desc) if pkg_desc else ""
            score = 0

            # Exact match on name or id (highest priority)
            if name_norm == q or id_norm == q:
                score += 500
            # Name or id starts with query
            elif name_norm.startswith(q) or id_norm.startswith(q):
                score += 300
            # Query is a word in name or id
            elif q in name_norm.split() or q in id_norm.split():
                score += 250
            # Name or id contains query
            elif q in name_norm or q in id_norm:
                score += 200

            # Query in description
            if q in desc_norm:
                score += 50

            # Word starts with query in name/id
            name_id_words = name_norm.split() + id_norm.split()
            if any(w.startswith(q) for w in name_id_words):
                score += 100

            # All tokens found in name/id/desc
            full_text = f"{name_norm} {id_norm} {desc_norm}"
            if all(t in full_text for t in q_tokens):
                score += 40

            # Related words
            if related_tokens and any(rt in full_text for rt in related_tokens):
                score += 25

            # Fuzzy match on name
            ratio = SequenceMatcher(None, q, name_norm).ratio()
            if ratio > 0.5:
                score += int(ratio * 50)

            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda item: (-item[0], item[1][2].lower()))
        return [row for _, row in scored[:limit]]

    @staticmethod
    def _norm(text: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    @staticmethod
    def _escape_markup(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _set_results(self, rows: list[tuple[str, str, str, str]]) -> None:
        self._results = rows
        self._install_row_progress.clear()
        while True:
            row = self._list.get_row_at_index(0)
            if row is None:
                break
            self._list.remove(row)
        for source, pkg_id, pkg_name, pkg_desc in rows:
            key = f"{source}:{pkg_id}"
            is_installed = self._is_pkg_installed(source, pkg_id)
            safe_name = self._escape_markup(pkg_name)
            safe_desc = self._escape_markup(pkg_desc) if pkg_desc else ""
            subtitle = f"{pkg_id} ({source})"
            if safe_desc:
                subtitle = f"{safe_desc} — {pkg_id} ({source})"
            if is_installed:
                subtitle = f"✓ Installed — {subtitle}"
            exp_row = Adw.ExpanderRow(title=safe_name, subtitle=subtitle)
            desc_label = Gtk.Label(label="Loading description...", wrap=True, xalign=0.0)
            desc_label.set_margin_start(12)
            desc_label.set_margin_end(12)
            desc_label.set_margin_top(6)
            desc_label.set_margin_bottom(12)
            desc_label.add_css_class("dim-label")
            exp_row.add_row(desc_label)
            exp_row.connect(
                "notify::expanded",
                self._on_row_expanded,
                source,
                pkg_id,
                desc_label,
            )
            if is_installed:
                badge = Gtk.Label(label="Installed")
                badge.add_css_class("dim-label")
                badge.set_valign(Gtk.Align.CENTER)
                exp_row.add_suffix(badge)
            else:
                check = Gtk.CheckButton()
                check.set_active(self._selected.get(key, False))
                check.connect("toggled", self._on_check_toggled, key)
                exp_row.add_suffix(check)
            pbar = Gtk.ProgressBar()
            pbar.set_show_text(True)
            pbar.set_visible(False)
            pbar.set_hexpand(True)
            pbar.set_margin_top(2)
            pbar.set_margin_bottom(4)
            outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            outer.append(exp_row)
            outer.append(pbar)
            self._install_row_progress[key] = pbar
            self._list.append(outer)
        first = self._list.get_row_at_index(0)
        if first is not None:
            schedule_scroll_widget_into_view(first)

    def _on_check_toggled(self, btn: Gtk.CheckButton, key: str) -> None:
        self._selected[key] = btn.get_active()

    def _on_row_expanded(
        self,
        exp_row: Adw.ExpanderRow,
        _pspec: Any,
        source: str,
        pkg_id: str,
        desc_label: Gtk.Label,
    ) -> None:
        if not exp_row.get_expanded():
            return
        key = f"{source}:{pkg_id}"
        cached = self._tooltip_cache.get(key)
        if cached and cached != "__loading__":
            desc_label.set_label(cached)
            return
        if cached == "__loading__":
            return
        self._tooltip_cache[key] = "__loading__"
        self._run_task(self._fetch_description_for_row(source, pkg_id, desc_label), "")

    async def _fetch_description_for_row(
        self, source: str, pkg_id: str, desc_label: Gtk.Label
    ) -> None:
        key = f"{source}:{pkg_id}"
        try:
            text = await self._installer.get_full_package_description(source, pkg_id)
            desc = text.strip() if text and text.strip() else f"No description available for {pkg_id}."
        except Exception:
            log.exception("Failed to fetch description for %s:%s", source, pkg_id)
            desc = f"Could not fetch description for {pkg_id}."
        self._tooltip_cache[key] = desc
        GLib.idle_add(desc_label.set_label, desc)

    def _on_install_selected(self, _btn: Gtk.Button) -> None:
        targets = [k for k, active in self._selected.items() if active]
        if not targets:
            emit_utility_toast("No packages selected.", "error")
            return
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            app.enqueue_task(self._install_targets(targets))  # type: ignore[attr-defined]
            return
        try:
            asyncio.get_event_loop().create_task(self._install_targets(targets))
        except RuntimeError:
            emit_utility_toast("Cannot run install without app background loop.", "error")

    def _apply_install_row_progress(self, key: str, msg: str, frac: float) -> None:
        bar = self._install_row_progress.get(key)
        if not bar:
            return
        bar.set_visible(True)
        f = min(1.0, max(0.0, frac))
        bar.set_fraction(f)
        bar.set_text(f"{int(f * 100)}%")
        if msg:
            bar.set_tooltip_text(msg)

    def _reset_install_row_progress(self, key: str) -> None:
        bar = self._install_row_progress.get(key)
        if not bar:
            return
        bar.set_visible(False)
        bar.set_fraction(0.0)
        bar.set_tooltip_text(None)

    def _make_install_progress_cb(self, key: str):
        def _cb(msg: str, frac: float) -> None:
            GLib.idle_add(self._apply_install_row_progress, key, msg, frac)

        return _cb

    async def _install_targets(self, targets: list[str]) -> None:
        GLib.idle_add(self._install_btn.set_sensitive, False)
        ok_count = 0
        newly_installed: list[str] = []
        try:
            for i, item in enumerate(targets):
                source, pkg_id = item.split(":", 1)
                key = item
                GLib.idle_add(
                    self._status.set_label,
                    f"Installing {pkg_id} ({i + 1}/{len(targets)})…",
                )
                ok = await self._installer.install_package_by_source(
                    pkg_id,
                    source,
                    progress_callback=self._make_install_progress_cb(key),
                )
                GLib.idle_add(self._reset_install_row_progress, key)
                if ok:
                    ok_count += 1
                    newly_installed.append(pkg_id)
                    self._selected.pop(item, None)
                else:
                    emit_utility_toast(f"Install failed: {pkg_id} ({source})", "error")
            if newly_installed:
                await self._resync_installed_ids_from_os()
                GLib.idle_add(self._refresh_apps_section)
        finally:
            GLib.idle_add(self._install_btn.set_sensitive, True)
            GLib.idle_add(self._status.set_label, f"Installed {ok_count}/{len(targets)}.")
        emit_utility_toast(f"Installed {ok_count}/{len(targets)} packages.", "info", timeout=6)

    async def _resync_installed_ids_from_os(self) -> None:
        """Re-read installed package IDs from the OS (authoritative)."""
        source = self._get_source()
        if not source:
            return
        ids = await self._get_installed_ids(source)
        GLib.idle_add(self._apply_installed_ids, ids)

    def _apply_installed_ids(self, ids: set[str]) -> None:
        self._installed_ids = ids
        self._on_filters_changed()

    @staticmethod
    def _refresh_apps_section() -> None:
        """Trigger a refresh on the Apps catalog view."""
        from ui.widgets.workstation.apps_panel import get_apps_catalog_instance

        inst = get_apps_catalog_instance()
        if inst:
            inst._start_load()


class WorkstationConfigOverviewPage(Adw.PreferencesPage):
    """Overview: descriptive entryway for machine configuration (Git, SSH, System)."""

    def __init__(
        self,
        *,
        on_focus_area: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._on_focus_area = on_focus_area
        self.set_title("Machine Configuration")

        info = Adw.PreferencesGroup(
            title="Overview",
            description=(
                "Personalize your development environment. "
                "Unlike the initial Setup Wizard, this hub is for ongoing, "
                "permanent configuration of your identity, keys, and system tweaks."
            ),
        )
        self.add(info)

        grp = Adw.PreferencesGroup(title="Quick Actions")
        self._append_nav_row(grp, "Git Identity", "Name, Email, Default Branch, and Editor.", "git")
        self._append_nav_row(grp, "SSH Identity", "Generate keys and copy your Public Key.", "ssh")
        self._append_nav_row(grp, "System Tuning", "Distro-specific mirror speed and OS optimizations.", "system")
        self._append_nav_row(grp, "Dotfiles and Aliases", "Shell aliases and sync folder setup.", "dotfiles")
        self.add(grp)

        wiz = Adw.PreferencesGroup(title="Initial Setup")
        row = Adw.ActionRow(
            title="Open Setup Wizard",
            subtitle="Switch to the bulk Machine Setup page.",
            activatable=True,
        )
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        row.connect("activated", lambda _r: navigate_main_window("machine-setup"))
        wiz.add(row)
        self.add(wiz)

    def _append_nav_row(self, grp: Adw.PreferencesGroup, title: str, sub: str, section_id: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=sub, activatable=True)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        row.connect("activated", lambda _r, sid=section_id: self._on_nav(sid))
        grp.add(row)

    def _on_nav(self, section_id: str) -> None:
        if self._on_focus_area:
            self._on_focus_area(section_id)
            emit_utility_toast(f"Config → {section_id}", "info", timeout=4)
        else:
            emit_utility_toast("Config navigation is not wired.", "error")


class WorkstationConfigRailPanel(Gtk.Box):
    """Configuration: Side-rail navigation for personal settings."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # ── Sidebar ──
        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.set_size_request(200, -1)
        self._list.connect("row-selected", self._on_row_selected)

        # ── Content ──
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
            hexpand=True,
            vexpand=True,
        )

        items = [
            ("git", "Git Identity", "vcs-normal-symbolic"),
            ("ssh", "SSH Identity", "network-vpn-symbolic"),
            ("system", "System Tuning", "system-run-symbolic"),
            ("dotfiles", "Dotfiles", "text-x-script-symbolic"),
        ]

        for sub_id, label, icon in items:
            row = self._make_row(sub_id, label, icon)
            self._list.append(row)
            self._stack.add_named(WorkstationCatalogPage("config", group_id=sub_id), sub_id)

        scrolled_nav = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled_nav.set_child(self._list)

        self.append(scrolled_nav)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.append(self._stack)

        GLib.idle_add(self._select_first)

    def _make_row(self, sub_id: str, label: str, icon_name: str) -> Gtk.ListBoxRow:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=label, xalign=0.0)
        lbl.set_hexpand(True)

        box.append(icon)
        box.append(lbl)

        row = Gtk.ListBoxRow(child=box)
        row.set_name(sub_id)
        return row

    def _select_first(self) -> None:
        row = self._list.get_row_at_index(0)
        if row:
            self._list.select_row(row)

    def _on_row_selected(self, _lb: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row:
            sid = row.get_name()
            if sid:
                self._stack.set_visible_child_name(sid)

    def goto_sub_tab(self, sub_id: str) -> bool:
        if sub_id in {"git", "ssh", "system", "dotfiles"}:
            i = 0
            while True:
                row = self._list.get_row_at_index(i)
                if not row:
                    break
                if row.get_name() == sub_id:
                    self._list.select_row(row)
                    return True
                i += 1
        return False


class WorkstationConfigPanel(Gtk.Box):
    """Personalize: Overview | Configure (Git, SSH, …) | CLI reference."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._bar: WorkstationSubsectionBar | None = None
        self._rail = WorkstationConfigRailPanel()

        def _focus_area(area: str) -> None:
            if self._bar and self._rail.goto_sub_tab(area):
                self._bar.switch_to_id("configure")

        overview = WorkstationConfigOverviewPage(on_focus_area=_focus_area)
        self._bar = WorkstationSubsectionBar(
            [
                ("overview", "Overview", overview),
                ("configure", "Configure", self._rail),
                ("cli", "CLI", DesktopCliReferencePage()),
            ]
        )
        self.append(self._bar)

    def goto_subsection(self, sub_id: str) -> bool:
        if not self._bar:
            return False
        if sub_id == "overview":
            return self._bar.switch_to_id("overview")
        if sub_id == "configure":
            return self._bar.switch_to_id("configure")
        if sub_id == "cli":
            return self._bar.switch_to_id("cli")
        if sub_id in {"git", "ssh", "system", "dotfiles"} and self._rail.goto_sub_tab(sub_id):
            return self._bar.switch_to_id("configure")
        return False

    def reset_subsections(self) -> None:
        if self._bar:
            self._bar.reset_to_first()


class WorkstationInstallOverviewPage(Gtk.Box):
    """Install hub overview: deep-links to AI, Services, and the Packages picker."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kwargs)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        root = Adw.PreferencesPage()
        grp = Adw.PreferencesGroup(
            title="Overview",
            description=(
                "Modern developer toolchains and terminal environments. Driven by data/workstation_catalog.json."
            ),
        )
        self._append_nav_row(grp, "Dev Toolchains", "Python, Rust, Go, Node.js, Java, C++.", "dev")
        self._append_nav_row(grp, "Editors", "VS Code, Cursor, Zed, Neovim, JetBrains.", "editors")
        self._append_nav_row(grp, "Terminals and shells", "Alacritty, Ghostty, Kitty, tmux, Zsh, Starship.", "terminal")
        self._append_nav_row(grp, "AI Tools", "Ollama, LM Studio, Open WebUI, Copilot CLI.", "ai")
        self._append_nav_row(
            grp,
            "Services Hub",
            "Docker, Tailscale, Dropbox, NordVPN, password managers.",
            "services",
        )
        pk = Adw.ActionRow(
            title="Packages (this hub)",
            subtitle="Switch to the Packages tab for Flatpak + distro search and multi-select install.",
        )
        pk.set_activatable(False)
        grp.add(pk)
        root.add(grp)
        self.append(root)

    def _append_nav_row(self, grp: Adw.PreferencesGroup, title: str, subtitle: str, section_id: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_activatable(True)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        row.connect("activated", lambda _r, sid=section_id: self._on_nav(sid))
        grp.add(row)

    def _on_nav(self, section_id: str) -> None:
        if not navigate_workstation_section(section_id):
            emit_utility_toast("Could not open that section.", "error")
        else:
            emit_utility_toast(f"Switched to {section_id}.", "info", timeout=4)



class WorkstationCatalogPage(Gtk.Box):
    """Populate catalog rows from ``workstation_catalog.json`` (install or remove mode)."""

    def __init__(
        self,
        category_id: str,
        *,
        mode: Literal["install", "remove"] = "install",
        group_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)
        self._category_id = category_id
        self._mode: Literal["install", "remove"] = mode
        self._group_id = group_id
        page = Adw.PreferencesPage()
        page.set_vexpand(False)
        entry = category_from_catalog(category_id)
        if entry is None:
            miss = Adw.PreferencesGroup(
                title="Catalog",
                description=f"No category {category_id!r} in workstation_catalog.json.",
            )
            page.add(miss)
            self.append(page)
            return

        groups = catalog_groups(entry, mode)
        if group_id:
            # Filter to specific group by ID or Title
            groups = [
                g
                for g in groups
                if isinstance(g, dict)
                and (str(g.get("id")) == group_id or str(g.get("title")).lower() == group_id.lower())
            ]

        if not groups:
            miss = Adw.PreferencesGroup(
                title="Catalog",
                description=f"No {mode} groups (filter: {group_id!r}) for category {category_id!r}.",
            )
            page.add(miss)
            self.append(page)
            return

        for group in groups:
            if not isinstance(group, dict):
                continue
            title = str(group.get("title", "Group"))
            desc = str(group.get("description", "") or "")
            g = Adw.PreferencesGroup(title=title, description=desc)
            rows = group.get("rows")
            if not isinstance(rows, list):
                page.add(g)
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                only = row.get("pm_only")
                if only and str(only) != _PKG_MANAGER:
                    continue
                rtype = str(row.get("type", "runnable") or "runnable")
                cmd = build_row_command(row, mode=mode)
                t = str(row.get("title", "Command"))
                chk = row.get("check_cmd")
                check = str(chk) if chk else None
                tag = row.get("tag")
                if rtype == "copy":
                    _add_one_copy_row(g, t, cmd)
                elif rtype == "terminal":
                    _add_terminal_row(g, t, cmd)
                else:
                    _add_runnable_row(g, t, cmd, check_cmd=check, tag=tag)
            page.add(g)

        self.append(page)


class WorkstationTerminalConfigPanel(Gtk.Box):
    """Terminal & Shell: Side-rail navigation for tool configurations."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # ── Sidebar ──
        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.set_size_request(200, -1)
        self._list.connect("row-selected", self._on_row_selected)

        # ── Content ──
        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
            hexpand=True,
            vexpand=True,
        )

        items = [
            ("alacritty", "Alacritty", "alacritty_cfg", "utilities-terminal-symbolic"),
            ("ghostty", "Ghostty", "ghostty_cfg", "terminal-multi-symbolic"),
            ("kitty", "Kitty", "kitty_cfg", "utilities-terminal-symbolic"),
            ("wezterm", "WezTerm", "wezterm_cfg", "utilities-terminal-symbolic"),
            ("tmux", "tmux", "tmux_cfg", "application-x-executable-symbolic"),
            ("zsh", "Zsh", "zsh_cfg", "utilities-terminal-symbolic"),
            ("starship", "Starship", "starship_cfg", "system-run-symbolic"),
        ]

        for sub_id, label, cat_id, icon in items:
            row = self._make_row(sub_id, label, icon)
            self._list.append(row)
            self._stack.add_named(WorkstationCatalogPage(cat_id, mode="install"), sub_id)

        scrolled_nav = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled_nav.set_child(self._list)

        self.append(scrolled_nav)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.append(self._stack)

        GLib.idle_add(self._select_first)

    def _make_row(self, sub_id: str, label: str, icon_name: str) -> Gtk.ListBoxRow:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=label, xalign=0.0)
        lbl.set_hexpand(True)

        box.append(icon)
        box.append(lbl)

        row = Gtk.ListBoxRow(child=box)
        row.set_name(sub_id)
        return row

    def _select_first(self) -> None:
        row = self._list.get_row_at_index(0)
        if row:
            self._list.select_row(row)

    def _on_row_selected(self, _lb: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row:
            sid = row.get_name()
            if sid:
                self._stack.set_visible_child_name(sid)

    def goto_sub_tab(self, sub_id: str) -> bool:
        if sub_id in {"alacritty", "ghostty", "kitty", "wezterm", "tmux", "zsh", "starship"}:
            i = 0
            while True:
                row = self._list.get_row_at_index(i)
                if not row:
                    break
                if row.get_name() == sub_id:
                    self._list.select_row(row)
                    return True
                i += 1
        return False


class WorkstationTerminalRemovePanel(Gtk.Box):
    """Remove terminal tools: same side-rail as Install, data from removal_groups in the catalog."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self._list.add_css_class("navigation-sidebar")
        self._list.set_size_request(200, -1)
        self._list.connect("row-selected", self._on_row_selected)

        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
            hexpand=True,
            vexpand=True,
        )

        items = [
            ("alacritty", "Alacritty", "alacritty_cfg", "utilities-terminal-symbolic"),
            ("ghostty", "Ghostty", "ghostty_cfg", "terminal-multi-symbolic"),
            ("kitty", "Kitty", "kitty_cfg", "utilities-terminal-symbolic"),
            ("wezterm", "WezTerm", "wezterm_cfg", "utilities-terminal-symbolic"),
            ("tmux", "tmux", "tmux_cfg", "application-x-executable-symbolic"),
            ("zsh", "Zsh", "zsh_cfg", "utilities-terminal-symbolic"),
            ("starship", "Starship", "starship_cfg", "system-run-symbolic"),
        ]

        for sub_id, label, cat_id, icon in items:
            row = self._make_row(sub_id, label, icon)
            self._list.append(row)
            self._stack.add_named(WorkstationCatalogPage(cat_id, mode="remove"), sub_id)

        scrolled_nav = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scrolled_nav.set_child(self._list)

        self.append(scrolled_nav)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.append(self._stack)

        GLib.idle_add(self._select_first)

    def _make_row(self, sub_id: str, label: str, icon_name: str) -> Gtk.ListBoxRow:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(10)
        box.set_margin_end(10)

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_valign(Gtk.Align.CENTER)
        lbl = Gtk.Label(label=label, xalign=0.0)
        lbl.set_hexpand(True)

        box.append(icon)
        box.append(lbl)

        row = Gtk.ListBoxRow(child=box)
        row.set_name(sub_id)
        return row

    def _select_first(self) -> None:
        row = self._list.get_row_at_index(0)
        if row:
            self._list.select_row(row)

    def _on_row_selected(self, _lb: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row:
            sid = row.get_name()
            if sid:
                self._stack.set_visible_child_name(sid)

    def goto_sub_tab(self, sub_id: str) -> bool:
        if sub_id in {"alacritty", "ghostty", "kitty", "wezterm", "tmux", "zsh", "starship"}:
            i = 0
            while True:
                row = self._list.get_row_at_index(i)
                if not row:
                    break
                if row.get_name() == sub_id:
                    self._list.select_row(row)
                    return True
                i += 1
        return False


class WorkstationInstallPanel(Gtk.Box):
    """Install: Overview | Dev | Editors | Neovim tips | Backend | Terminal | Packages."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._term_cfg = WorkstationTerminalConfigPanel()
        self._bar = WorkstationSubsectionBar(
            [
                ("overview", "Overview", WorkstationInstallOverviewPage()),
                ("dev", "Dev", WorkstationCatalogPage("dev")),
                ("editors", "Editors", WorkstationCatalogPage("editors")),
                ("neovim", "Neovim", NeovimCheatsheetPage()),
                ("backend", "Backend", BackendIssuesPage()),
                ("terminal", "Terminal", self._term_cfg),
                ("packages", "Packages", WorkstationInstallPackagesPage()),
            ]
        )
        self.append(self._bar)

    def goto_subsection(self, sub_id: str) -> bool:
        """Called by WorkstationPage deep-linking."""
        if sub_id == "terminals":
            self._bar.switch_to_id("terminal")
            return True
        if sub_id in {"overview", "dev", "editors", "neovim", "backend", "terminal", "packages"}:
            self._bar.switch_to_id(sub_id)
            return True

        if self._term_cfg.goto_sub_tab(sub_id):
            self._bar.switch_to_id("terminal")
            return True

        return False

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


class WorkstationRemoveOverviewPage(Gtk.Box):
    """Remove hub overview: same tab layout as Install; jump into Dev, Editors, Terminal rail, or Cleanup."""

    def __init__(self, *, on_nav_sub: Callable[[str], None], **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kwargs)
        self._on_nav_sub = on_nav_sub
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        root = Adw.PreferencesPage()
        grp = Adw.PreferencesGroup(
            title="Overview",
            description=(
                "Uninstall flows mirror the Install hub and are driven by data/workstation_catalog.json "
                "(removal_groups and cleanup). Use Terminal for per-tool removal with the side rail."
            ),
        )
        self._append_row(grp, "Dev stacks", "Python, Rust, Go, Node, Java, toolchains.", "dev")
        self._append_row(grp, "Editors", "VS Code, Neovim, JetBrains, Flatpak/distro uninstall.", "editors")
        self._append_row(grp, "Terminal tools", "Alacritty, Kitty, WezTerm, tmux, Zsh, Starship (side rail).", "terminal")
        self._append_row(grp, "Cleanup", "Package templates, caches, logs, disk usage.", "cleanup")
        pk = Adw.ActionRow(
            title="Interactive packages",
            subtitle="For searchable multi-select install or removal, use Tools → Install → Packages.",
        )
        pk.set_activatable(True)
        pk.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        pk.connect("activated", self._on_packages_hint)
        grp.add(pk)
        root.add(grp)
        self.append(root)

    def _append_row(self, grp: Adw.PreferencesGroup, title: str, subtitle: str, sub_id: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_activatable(True)
        row.add_suffix(Gtk.Image.new_from_icon_name("go-next-symbolic"))
        row.connect("activated", lambda _r, sid=sub_id: self._on_sub(sid))
        grp.add(row)

    def _on_sub(self, sub_id: str) -> None:
        self._on_nav_sub(sub_id)
        emit_utility_toast(f"Remove → {sub_id}", "info", timeout=4)

    def _on_packages_hint(self, *_args: Any) -> None:
        if navigate_workstation_section("install"):
            emit_utility_toast("Switched to Install. Open the Packages tab there.", "info", timeout=5)
        else:
            emit_utility_toast("Could not open Install.", "error")


class WorkstationRemovePanel(Gtk.Box):
    """Remove: Overview | Dev | Editors | Terminal (rail) | Cleanup — catalog-driven."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._bar: WorkstationSubsectionBar | None = None
        self._term_rm = WorkstationTerminalRemovePanel()

        def _nav_sub(sub_id: str) -> None:
            if self._bar and self._bar.switch_to_id(sub_id):
                return

        overview = WorkstationRemoveOverviewPage(on_nav_sub=_nav_sub)
        self._bar = WorkstationSubsectionBar(
            [
                ("overview", "Overview", overview),
                ("dev", "Dev", WorkstationCatalogPage("dev", mode="remove")),
                ("editors", "Editors", WorkstationCatalogPage("editors", mode="remove")),
                ("terminal", "Terminal", self._term_rm),
                ("cleanup", "Cleanup", WorkstationCatalogPage("cleanup", mode="remove")),
            ]
        )
        self.append(self._bar)

    def goto_subsection(self, sub_id: str) -> bool:
        """Deep-link from WorkstationPage (``remove:cleanup``, ``remove:alacritty``, …)."""
        if not self._bar:
            return False
        if sub_id in ("overview", "dev", "editors", "terminal", "cleanup"):
            return self._bar.switch_to_id(sub_id)
        if self._term_rm.goto_sub_tab(sub_id):
            return self._bar.switch_to_id("terminal")
        return False

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()
