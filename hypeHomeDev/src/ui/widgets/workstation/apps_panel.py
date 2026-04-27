"""Workstation hub — Apps: left sidebar area; subsections via top bar (StackSwitcher)."""

from __future__ import annotations

import asyncio
import re
import logging
from difflib import SequenceMatcher
from typing import Any, cast

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.models import AppInfo  # noqa: E402
from core.setup.package_installer import PackageInstaller  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.nav_helper import navigate_main_window  # noqa: E402
from ui.widgets.workstation.subsection_bar import WorkstationSubsectionBar  # noqa: E402
from ui.widgets.workstation.workstation_learning_scroll import (
    schedule_scroll_widget_into_view,  # noqa: E402
)

log = logging.getLogger(__name__)

_UI_CATEGORY_ORDER: list[str] = [
    "all apps",
    "accessories",
    "graphic",
    "internet",
    "office",
    "sound & video",
    "administration",
    "preferences",
    "flatpak",
    "container",
    "manual",
]


_apps_catalog_instance: WorkstationAppsCatalogView | None = None


def get_apps_catalog_instance() -> WorkstationAppsCatalogView | None:
    return _apps_catalog_instance


class WorkstationAppsCatalogView(Gtk.Box):
    """Installed apps: intro, search, list, status (scroll is provided by subsection shell)."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        global _apps_catalog_instance
        _apps_catalog_instance = self
        self._executor = HostExecutor()
        self._host_access = not self._executor.is_flatpak
        self._installer = PackageInstaller(self._executor, native_host_access=self._host_access)
        self._apps: list[AppInfo] = []
        self._removing: set[str] = set()
        self._app_row_progress: dict[str, Gtk.ProgressBar] = {}
        self._search_query = ""
        self._smart_search_cache: list[AppInfo] = []
        self._search_debounce_ms = 250
        self._search_debounce_source_id: int | None = None
        self._is_alive = True
        self._category_filter = "all apps"
        self._category_values: list[str] = ["all apps"]

        self._list = Gtk.ListBox()
        self._list.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list.add_css_class("boxed-list")

        self._search = Gtk.SearchEntry()
        self._search.set_placeholder_text("Filter by name or description…")
        self._search.connect("search-changed", self._on_search_changed)
        category_model = Gtk.StringList.new(["all apps"])
        self._category = Gtk.DropDown(model=category_model)
        self._category.set_selected(0)
        self._category.connect("notify::selected", self._on_category_changed)

        self._refresh_btn = Gtk.Button(label="Refresh")
        self._refresh_btn.connect("clicked", self._on_refresh_clicked)

        page_intro = Adw.PreferencesPage()
        page_intro.set_vexpand(False)
        intro_group = Adw.PreferencesGroup(
            title="Installed apps",
            description=(
                "Shows apps detected from your installed package managers "
                "(dnf, apt, pacman, zypper, apk, Flatpak)."
            ),
        )
        # Native host access toggle (Flatpak sandbox-friendly).
        # When OFF, native (non-Flatpak) remove actions are locked but rows stay visible.
        host_switch = Gtk.Switch()
        host_switch.set_halign(Gtk.Align.CENTER)
        host_switch.set_valign(Gtk.Align.CENTER)
        host_switch.set_active(self._host_access)

        def _on_host_access_toggled(sw: Gtk.Switch, pspec: Any) -> None:
            self._host_access = sw.get_active()
            self._installer.set_native_host_access_enabled(self._host_access)
            self._rebuild_rows()

        host_switch.connect("notify::active", _on_host_access_toggled)
        host_subtitle = (
            "Enable managing native packages via apt/dnf/etc. "
            "When running in Flatpak sandbox, this may be unavailable."
        )
        if self._executor.is_flatpak:
            host_subtitle = "Flatpak sandbox: native host access is OFF by default."
        host_row = Adw.ActionRow(
            title="Host Access",
            subtitle=host_subtitle,
        )
        host_row.add_suffix(host_switch)
        intro_group.add(host_row)

        intro_group.set_header_suffix(self._refresh_btn)
        page_intro.add(intro_group)

        list_scroll = Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            min_content_height=160,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        try:
            list_scroll.set_overlay_scrolling(False)
        except (AttributeError, TypeError):
            pass
        list_scroll.set_child(self._list)

        self._status = Gtk.Label(label="Loading installed apps…")
        self._status.set_xalign(0.0)
        self._status.add_css_class("dim-label")
        self._status.set_margin_start(18)
        self._status.set_margin_end(18)
        self._status.set_margin_top(6)
        self._status.set_margin_bottom(12)

        self._search.set_margin_start(18)
        self._search.set_margin_end(18)
        self._search.set_margin_top(8)
        self._search.set_margin_bottom(6)
        self._category.set_margin_start(18)
        self._category.set_margin_end(18)
        self._category.set_margin_top(0)
        self._category.set_margin_bottom(6)
        list_scroll.set_margin_start(12)
        list_scroll.set_margin_end(12)

        self.append(page_intro)
        self.append(self._search)
        self.append(self._category)
        self.append(list_scroll)
        self.append(self._status)

        GLib.idle_add(self._start_load)

    def do_unrealize(self) -> None:
        """Cleanup debouncer and background state when widget is torn down."""
        self._is_alive = False
        if self._search_debounce_source_id:
            GLib.source_remove(self._search_debounce_source_id)
            self._search_debounce_source_id = None
        Gtk.Box.do_unrealize(self)

    def _start_load(self) -> bool:
        self._refresh_btn.set_sensitive(False)
        self._status.set_label("Loading installed apps…")
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            cast(Any, app).enqueue_task(self._load_catalog())
        else:
            try:
                asyncio.get_event_loop().create_task(self._load_catalog())
            except RuntimeError:
                self._status.set_label("Background loop unavailable; start the full app to load apps.")
                self._refresh_btn.set_sensitive(True)
                log.warning("WorkstationAppsCatalogView: no enqueue_task and no asyncio loop")
        return False

    def _on_refresh_clicked(self, _btn: Gtk.Button) -> None:
        self._start_load()

    async def _load_catalog(self) -> None:
        ok = await self._installer.initialize()
        if not ok:
            GLib.idle_add(self._status.set_label, "Could not initialize app detection (package managers).")
            return
        try:
            installed_apps = await self._installer.get_installed_packages(include_container_apps=True)
        except Exception:
            log.exception("WorkstationAppsCatalogView: failed to load installed apps")
            GLib.idle_add(self._status.set_label, "Failed to read installed app state.")
            return
        GLib.idle_add(self._apply_loaded_apps, installed_apps)

    def _apply_loaded_apps(self, apps: list[AppInfo]) -> None:
        if not self._is_alive:
            return
        self._apps = apps
        self._reload_category_filter()
        if apps:
            self._status.set_label(f"{len(apps)} installed apps found.")
        else:
            self._status.set_label("No installed apps from the catalog were detected.")
        self._rebuild_rows()
        self._refresh_btn.set_sensitive(True)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self._search_query = (entry.get_text() or "").strip()
        if self._search_debounce_source_id is not None:
            GLib.source_remove(self._search_debounce_source_id)
        self._search_debounce_source_id = GLib.timeout_add(
            self._search_debounce_ms, self._apply_search_debounced
        )

    def _apply_search_debounced(self) -> bool:
        self._search_debounce_source_id = None
        # Rebuild list rows for debounced search query.
        self._rebuild_rows()
        return False

    def _on_category_changed(self, _dropdown: Gtk.DropDown, _pspec: Any) -> None:
        if self._search_debounce_source_id is not None:
            GLib.source_remove(self._search_debounce_source_id)
            self._search_debounce_source_id = None
        selected = self._category.get_selected()
        if selected < len(self._category_values):
            self._category_filter = self._category_values[selected]
        else:
            self._category_filter = "all"
        self._rebuild_rows()

    def _reload_category_filter(self) -> None:
        found = {(a.ui_category or "all apps").strip().lower() for a in self._apps}
        categories = [c for c in _UI_CATEGORY_ORDER if c == "all apps" or c in found]
        labels = categories
        self._category_values = categories
        self._category.set_model(Gtk.StringList.new(labels))
        if self._category_filter not in self._category_values:
            self._category_filter = "all apps"
        self._category.set_selected(self._category_values.index(self._category_filter))

    def _filtered_apps(self) -> list[AppInfo]:
        apps = self._apps
        if self._category_filter != "all apps":
            apps = [
                a
                for a in apps
                if (a.ui_category or "all apps").strip().lower() == self._category_filter
            ]

        q = (self._search_query or "").strip()
        if not q:
            return apps

        return self._smart_filter_apps(q, apps, limit=300)

    @staticmethod
    def _norm(text: str) -> str:
        # Keep it aligned with WorkstationInstallPackagesPage smart search.
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

    def _smart_filter_apps(
        self,
        query: str,
        apps: list[AppInfo],
        *,
        limit: int = 300,
    ) -> list[AppInfo]:
        q = self._norm(query)
        q_tokens = [t for t in q.split() if t]
        if not q_tokens:
            return apps[:limit]

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

        scored: list[tuple[int, AppInfo]] = []
        for app in apps:
            name_norm = self._norm(app.name)
            id_norm = self._norm(app.id)
            desc_norm = self._norm(app.description) if app.description else ""

            score = 0
            if name_norm == q or id_norm == q:
                score += 500
            elif name_norm.startswith(q) or id_norm.startswith(q):
                score += 300
            elif q in name_norm.split() or q in id_norm.split():
                score += 250
            elif q in name_norm or q in id_norm:
                score += 200

            if q in desc_norm:
                score += 50

            name_id_words = name_norm.split() + id_norm.split()
            if any(w.startswith(q) for w in name_id_words):
                score += 100

            full_text = f"{name_norm} {id_norm} {desc_norm}"
            if all(t in full_text for t in q_tokens):
                score += 40

            if related_tokens and any(rt in full_text for rt in related_tokens):
                score += 25

            ratio = SequenceMatcher(None, q, name_norm).ratio()
            if ratio > 0.5:
                score += int(ratio * 50)

            if score > 0:
                scored.append((score, app))

        scored.sort(key=lambda item: (-item[0], item[1].name.lower()))
        return [app for _score, app in scored[:limit]]

    def _rebuild_rows(self) -> None:
        self._app_row_progress.clear()
        while True:
            row = self._list.get_row_at_index(0)
            if row is None:
                break
            self._list.remove(row)
        for app in self._filtered_apps():
            self._list.append(self._make_app_row(app))
        first = self._list.get_row_at_index(0)
        if first is not None:
            schedule_scroll_widget_into_view(first)

    def _make_app_row(self, app: AppInfo) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_name(app.id)
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(8)
        box.set_margin_bottom(4)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Icon (symbolic icon name or filename).
        icon: Gtk.Widget
        if "/" in (app.icon or "") or (app.icon or "").endswith((".png", ".svg", ".jpg", ".jpeg")):
            pic = Gtk.Picture.new_for_filename(app.icon)
            pic.set_can_shrink(True)
            pic.set_size_request(48, 48)
            pic.set_keep_aspect_ratio(True)
            pic.set_content_fit(Gtk.ContentFit.CONTAIN)
            icon = pic
        else:
            img = Gtk.Image.new_from_icon_name(app.icon)
            img.set_size_request(48, 48)
            if hasattr(img, "set_pixel_size"):
                img.set_pixel_size(32)
            icon = img
        icon.set_valign(Gtk.Align.CENTER)
        icon.set_halign(Gtk.Align.CENTER)
        icon.set_hexpand(False)
        box.append(icon)

        text_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        text_col.set_hexpand(True)
        title = Gtk.Label(label=app.name, xalign=0.0)
        title.add_css_class("heading")
        sub = Gtk.Label(label=app.description, xalign=0.0)
        sub.add_css_class("caption")
        sub.add_css_class("dim-label")
        sub.set_wrap(True)
        sub.set_natural_wrap_mode(True)
        meta = Gtk.Label(
            label=f"{app.package_name}" + (f" · flatpak:{app.flatpak_id}" if app.flatpak_id else ""),
            xalign=0.0,
        )
        meta.add_css_class("dim-label")
        meta.set_wrap(True)
        text_col.append(title)
        text_col.append(sub)
        text_col.append(meta)

        source_kind = (app.category or "system").strip().lower()
        is_flatpak = source_kind == "flatpak"
        is_manual_or_system = source_kind in {"manual", "system"}
        is_container = source_kind == "container"
        locked_native = (not is_flatpak) and (not is_manual_or_system) and (not is_container) and (not self._host_access)

        if is_flatpak:
            badge_text = "[Flatpak]"
        elif is_manual_or_system:
            badge_text = "[System]" if source_kind == "system" else "[Manual]"
        elif is_container:
            badge_text = f"[Container: {app.package_name}]"
        else:
            badge_text = "[Native]" if self._host_access else "[Native (Host Access Required)]"

        if is_container:
            source = Gtk.Label(label=badge_text)
            source.add_css_class("caption")
            source.set_valign(Gtk.Align.CENTER)
        else:
            source = Gtk.Label(label=f"{badge_text} Source: {source_kind}")
            source.add_css_class("caption")
            source.add_css_class("workstation-source-label")
            source.set_valign(Gtk.Align.CENTER)
        remove_btn = Gtk.Button(label="Remove")
        remove_btn.add_css_class("destructive-action")
        remove_btn.set_valign(Gtk.Align.CENTER)

        # Action gating:
        # - Flatpaks always removable.
        # - Native/system removal requires Host Access (unless Container).
        # - Container apps are read-only in the host UI.
        if is_manual_or_system:
            remove_btn.set_sensitive(False)
            remove_btn.set_tooltip_text("Manual/system app: remove outside package manager.")
        elif is_container:
            remove_btn.set_sensitive(False)
            remove_btn.set_tooltip_text("Container apps are read-only. Export them via Machine Setup if needed.")
        elif locked_native:
            remove_btn.set_sensitive(False)
            if self._executor.is_flatpak:
                remove_btn.set_tooltip_text(
                    "Sandboxed Flatpak: Native (Host Access Required). Enable 'Host Access' in the Catalog to manage system packages."
                )
            else:
                remove_btn.set_tooltip_text(
                    "Native (Host Access Required). Enable 'Host Access' in the Catalog to manage native packages."
                )
        else:
            remove_btn.connect("clicked", self._on_remove_clicked, (app, remove_btn))

        if locked_native:
            # Row click nudge (even though Remove is disabled).
            gesture = Gtk.GestureClick()

            def _on_row_press(*_args: Any) -> None:
                if self._executor.is_flatpak:
                    msg = (
                        "This app is running in a sandbox. To manage system packages, enable 'Host Access' in the Catalog settings."
                    )
                else:
                    msg = (
                        "Native (Host Access Required). Enable 'Host Access' in the Catalog settings to manage native packages."
                    )
                emit_utility_toast(msg, "warning", timeout=6)

            gesture.connect("pressed", _on_row_press)
            row.add_controller(gesture)

        installed = Gtk.Button(label="Installed")
        installed.set_sensitive(False)
        installed.set_valign(Gtk.Align.CENTER)
        box.append(text_col)
        box.append(source)
        box.append(remove_btn)
        box.append(installed)
        pbar = Gtk.ProgressBar()
        pbar.set_show_text(True)
        pbar.set_visible(False)
        pbar.set_hexpand(True)
        pbar.set_margin_start(12)
        pbar.set_margin_end(12)
        pbar.set_margin_bottom(8)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.append(box)
        outer.append(pbar)
        row.set_child(outer)
        self._app_row_progress[app.id] = pbar
        return row

    def _app_is_remove_locked(self, app: AppInfo) -> bool:
        """Native (non-Flatpak) removals are locked unless Host Access is enabled."""
        source_kind = (app.category or "system").strip().lower()
        if source_kind == "container":
            return True
        is_flatpak = source_kind == "flatpak"
        is_manual_or_system = source_kind in {"manual", "system"}
        if is_manual_or_system:
            return True
        return (not is_flatpak) and (not self._host_access)

    def _on_remove_clicked(self, _btn: Gtk.Button, data: tuple[AppInfo, Gtk.Button]) -> None:
        app, remove_btn = data
        if app.id in self._removing:
            return

        if self._app_is_remove_locked(app):
            if self._executor.is_flatpak:
                msg = (
                    "This app is running in a sandbox. To manage system packages, enable 'Host Access' in the Catalog settings."
                )
            else:
                msg = (
                    "Native (Host Access Required). Enable 'Host Access' in the Catalog settings to manage system packages."
                )
            emit_utility_toast(msg, "warning", timeout=6)
            return

        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        source_kind = (app.category or "system").strip().lower()
        is_flatpak = source_kind == "flatpak"
        dlg = Adw.MessageDialog(
            transient_for=parent,
            heading=f"Remove {app.name}?",
            body=(
                "This will uninstall the Flatpak app from your system."
                if is_flatpak
                else "This will uninstall the app from your system (requires Host Access for native packages)."
            ),
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("remove", "Remove")
        dlg.set_response_appearance("remove", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")

        def _on_response(_d: Adw.MessageDialog, response: str) -> None:
            _d.destroy()
            if response != "remove":
                return

            gapp = Gtk.Application.get_default()
            if gapp and hasattr(gapp, "enqueue_task"):
                cast(Any, gapp).enqueue_task(self._remove_app(app, remove_btn))
                return
            try:
                asyncio.get_event_loop().create_task(self._remove_app(app, remove_btn))
            except RuntimeError:
                emit_utility_toast("Cannot run remove without app background loop.", "error")

        dlg.connect("response", _on_response)
        dlg.present()

    def _apply_remove_row_progress(self, app_id: str, msg: str, frac: float) -> None:
        bar = self._app_row_progress.get(app_id)
        if not bar:
            return
        bar.set_visible(True)
        f = min(1.0, max(0.0, frac))
        bar.set_fraction(f)
        bar.set_text(f"{int(f * 100)}%")
        if msg:
            bar.set_tooltip_text(msg)

    def _reset_remove_row_progress(self, app_id: str) -> None:
        bar = self._app_row_progress.get(app_id)
        if not bar:
            return
        bar.set_visible(False)
        bar.set_fraction(0.0)
        bar.set_tooltip_text(None)

    def _make_remove_progress_cb(self, app_id: str):
        def _cb(msg: str, frac: float) -> None:
            GLib.idle_add(self._apply_remove_row_progress, app_id, msg, frac)

        return _cb

    async def _remove_app(self, app: AppInfo, remove_btn: Gtk.Button) -> None:
        self._removing.add(app.id)

        def _busy() -> None:
            remove_btn.set_sensitive(False)
            remove_btn.set_label("Removing…")

        GLib.idle_add(_busy)
        ok = False
        err_msg: str | None = None
        try:
            ok = await self._installer.remove_installed_app(
                app, progress_callback=self._make_remove_progress_cb(app.id)
            )
        except Exception as e:
            log.exception("WorkstationAppsCatalogView: remove %s", app.id)
            err_msg = str(e)[:200] if str(e) else type(e).__name__
        finally:
            GLib.idle_add(self._reset_remove_row_progress, app.id)

        def _done() -> None:
            self._removing.discard(app.id)
            if err_msg:
                emit_utility_toast(f"Remove error for {app.name}: {err_msg}", "error")
                remove_btn.set_sensitive(True)
                remove_btn.set_label("Remove")
                return
            if ok:
                self._apps = [a for a in self._apps if a.id != app.id]
                self._reload_category_filter()
                self._rebuild_rows()
                self._status.set_label(f"{len(self._apps)} installed apps found.")
                emit_utility_toast(f"Removed {app.name}.", "info", timeout=6)
                self._refresh_install_section(app)
                return
            emit_utility_toast(f"Could not remove {app.name}.", "error")
            remove_btn.set_sensitive(True)
            remove_btn.set_label("Remove")

        GLib.idle_add(_done)

    @staticmethod
    def _refresh_install_section(_app: AppInfo) -> None:
        """Re-sync Install list with what is actually installed on the host."""
        from ui.widgets.workstation.panels import _install_page_instance

        inst = _install_page_instance
        if inst is None:
            return
        inst._run_task(inst._resync_installed_ids_from_os(), "")


class WorkstationAppsConfigView(Adw.PreferencesPage):
    """Post-install configuration links."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        g = Adw.PreferencesGroup(
            title="After install",
            description=(
                "Defaults and persistence under ~/.config where applicable; edit in each app or Utilities. "
                "Batch steps also live in Machine Setup."
            ),
        )
        row_ms = Adw.ActionRow(
            title="Machine Setup",
            subtitle="Wizard: git, dev folder, apps, repos, sync, configuration.",
            activatable=True,
        )
        row_ms.connect("activated", self._on_open_machine_setup)
        g.add(row_ms)
        row_u = Adw.ActionRow(
            title="Utilities",
            subtitle="Hosts, environment variables, and other host-level tweaks.",
            activatable=True,
        )
        row_u.connect("activated", self._on_open_utilities)
        g.add(row_u)
        self.add(g)

    def _on_open_machine_setup(self, *_args: Any) -> None:
        if not navigate_main_window("machine-setup"):
            emit_utility_toast("Could not open Machine Setup.", "error")

    def _on_open_utilities(self, *_args: Any) -> None:
        if not navigate_main_window("utilities"):
            emit_utility_toast("Could not open Utilities.", "error")


class WorkstationAppsPanel(Gtk.Box):
    """Apps: Catalog + Setup subsections."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._catalog = WorkstationAppsCatalogView()
        self._setup = WorkstationAppsConfigView()
        self._bar = WorkstationSubsectionBar(
            [
                ("catalog", "Catalog", self._catalog),
                ("setup", "Setup", self._setup),
            ]
        )
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()
