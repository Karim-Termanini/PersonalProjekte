"""HypeDevHome — Desktop Configuration Widget.

Applies GNOME GSettings for theme, font scaling, animations, and edge tiling when available.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

from core.utils.desktop_manager import DesktopManager  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402

log = logging.getLogger(__name__)


class DesktopConfig(Gtk.Box):
    """Personalization settings for the desktop environment."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._manager = DesktopManager()
        self._syncing_ui = False
        self._edit_enabled = False
        self._build_ui()

    def _enqueue_async(self, coro: Any) -> None:
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            cast(Any, app).enqueue_task(coro)
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(coro)
            else:
                self._enqueue_async_task = loop.create_task(coro)

    def _build_ui(self) -> None:
        """Assemble the configuration layout."""
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_margin_top(12)
        self.set_margin_bottom(12)

        self._outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._hint_host = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._hint_host.set_visible(False)
        self._hint_host.set_margin_bottom(8)
        self._outer.append(self._hint_host)

        page = Adw.PreferencesPage()

        safety = Adw.PreferencesGroup(
            title="Safety",
            description="Phase 5: preview is read-only until you enable edits (avoids accidental changes).",
        )
        self._edit_row = Adw.SwitchRow(
            title="Allow editing",
            subtitle="Turn on to apply GNOME settings from this page",
            active=False,
        )
        self._edit_row.connect("notify::active", self._on_edit_toggled)
        safety.add(self._edit_row)
        page.add(safety)

        # --- Appearance ---
        app_group = Adw.PreferencesGroup(
            title="Appearance", description="Look and feel of your desktop"
        )

        self._theme_row = Adw.ComboRow(
            title="Desktop Theme",
            subtitle="Switch between light and dark system themes (GNOME)",
            model=Gtk.StringList.new(["Dark", "Light", "System Default"]),
        )
        app_group.add(self._theme_row)

        self._font_row = Adw.ActionRow(
            title="System Font Size", subtitle="Adjust text scaling for UI (GNOME)"
        )
        self._font_spin = Gtk.SpinButton.new_with_range(8, 24, 1)
        self._font_spin.set_value(11)
        self._font_spin.set_valign(Gtk.Align.CENTER)
        self._font_row.add_suffix(self._font_spin)
        app_group.add(self._font_row)

        page.add(app_group)

        # --- Window Management ---
        wm_group = Adw.PreferencesGroup(
            title="Window Management", description="Workflow and productivity settings"
        )

        self._anim_row = Adw.SwitchRow(
            title="Enable Animations",
            subtitle="Use smooth transitions for windows and workspace switches",
            active=True,
        )
        wm_group.add(self._anim_row)

        self._tiling_row = Adw.SwitchRow(
            title="Tiling Layouts",
            subtitle="Edge tiling / snap-to-edge (GNOME Mutter)",
            active=False,
        )
        wm_group.add(self._tiling_row)

        page.add(wm_group)

        self._outer.append(page)
        self.append(self._outer)

        self._theme_row.connect("notify::selected", self._on_theme_changed)
        self._font_spin.connect("value-changed", self._on_font_changed)
        self._anim_row.connect("notify::active", self._on_anim_changed)
        self._tiling_row.connect("notify::active", self._on_tiling_changed)

        GLib.idle_add(self._start_initial_load)

    def _on_edit_toggled(self, _row: Adw.SwitchRow, _pspec: Any) -> None:
        self._edit_enabled = self._edit_row.get_active()
        self._apply_edit_sensitivity()

    def _apply_edit_sensitivity(self) -> None:
        en = self._edit_enabled
        status = self._manager.get_status()
        has_iface = bool(status.get("has_gnome_interface"))
        has_mutter = bool(status.get("has_gnome_mutter"))
        self._theme_row.set_sensitive(en and has_iface)
        self._font_row.set_sensitive(en and has_iface)
        self._font_spin.set_sensitive(en and has_iface)
        self._anim_row.set_sensitive(en and has_iface)
        self._tiling_row.set_sensitive(en and has_mutter)

    def _start_initial_load(self) -> bool:
        self._enqueue_async(self._load_settings())
        return False

    async def _load_settings(self) -> None:
        await self._manager.initialize()
        self._syncing_ui = True
        try:
            self._theme_row.set_selected(self._manager.get_theme_index())
            self._font_spin.set_value(float(self._manager.get_font_size_spin()))
            self._anim_row.set_active(self._manager.get_animations_enabled())
            self._tiling_row.set_active(self._manager.get_edge_tiling_enabled())
        finally:
            self._syncing_ui = False

        status = self._manager.get_status()
        has_iface = bool(status.get("has_gnome_interface"))

        self._apply_edit_sensitivity()

        self._refresh_desktop_hints()

        if not has_iface:
            log.info(
                "Desktop appearance controls need org.gnome.desktop.interface (session: %s).",
                status.get("session_label", "?"),
            )

    def _refresh_desktop_hints(self) -> None:
        """Show inline help when GNOME GSettings backends are missing (KDE, other distros, etc.)."""
        while True:
            child = self._hint_host.get_first_child()
            if not child:
                break
            self._hint_host.remove(child)

        paragraphs = self._manager.desktop_hint_paragraphs()
        if not paragraphs:
            self._hint_host.set_visible(False)
            return

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("card")
        card.set_margin_start(0)
        card.set_margin_end(0)
        m = 12
        card.set_margin_top(m)
        card.set_margin_bottom(m)
        card.set_margin_start(m)
        card.set_margin_end(m)

        title = Gtk.Label(
            label="Desktop integration",
            xalign=0.0,
        )
        title.add_css_class("heading")
        card.append(title)

        for p in paragraphs:
            body = Gtk.Label(label=p, xalign=0.0)
            body.set_wrap(True)
            body.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            body.add_css_class("dim-label")
            card.append(body)

        self._hint_host.append(card)
        self._hint_host.set_visible(True)

    def _on_theme_changed(self, _row: Adw.ComboRow, _pspec: Any) -> None:
        if self._syncing_ui or not self._edit_enabled:
            return
        if not self._manager.set_theme_index(int(self._theme_row.get_selected())):
            emit_utility_toast(
                "Could not apply desktop theme (GNOME settings unavailable or denied)."
            )

    def _on_font_changed(self, _spin: Gtk.SpinButton) -> None:
        if self._syncing_ui or not self._edit_enabled:
            return
        if not self._manager.set_font_size_spin(int(self._font_spin.get_value_as_int())):
            emit_utility_toast(
                "Could not change font scaling (GNOME settings unavailable or denied)."
            )

    def _on_anim_changed(self, _row: Adw.SwitchRow, _pspec: Any) -> None:
        if self._syncing_ui or not self._edit_enabled:
            return
        if not self._manager.set_animations_enabled(self._anim_row.get_active()):
            emit_utility_toast(
                "Could not change animation setting (GNOME settings unavailable or denied)."
            )

    def _on_tiling_changed(self, _row: Adw.SwitchRow, _pspec: Any) -> None:
        if self._syncing_ui or not self._edit_enabled:
            return
        if not self._manager.set_edge_tiling_enabled(self._tiling_row.get_active()):
            emit_utility_toast(
                "Could not change edge tiling (Mutter settings unavailable or denied)."
            )
