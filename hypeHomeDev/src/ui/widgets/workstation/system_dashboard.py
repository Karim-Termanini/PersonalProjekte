"""HypeDevHome — System Dashboard.

Unified "Front Door" for the Workstation hub. 
Features outcome-based wizards and system health summaries.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.power_installer import PowerInstaller  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.workstation_utils import _bg  # noqa: E402

log = logging.getLogger(__name__)


def _margin_all(widget: Gtk.Widget, margin: int) -> None:
    """GTK4 widgets have no ``set_margin_all``; set uniform margins explicitly."""
    widget.set_margin_top(margin)
    widget.set_margin_bottom(margin)
    widget.set_margin_start(margin)
    widget.set_margin_end(margin)


class OutcomeWizardCard(Gtk.Button):
    """Card representing a setup wizard (Outcome Profile).

    The whole card is one activatable button — no nested ``Gtk.Button`` children (GTK HIG).
    """

    def __init__(self, profile: Any) -> None:
        super().__init__()
        self.profile = profile
        self.add_css_class("flat")
        self.add_css_class("outcome-card")
        self.set_tooltip_text(profile.description)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        _margin_all(content, 16)

        icon = Gtk.Image.new_from_icon_name(profile.icon)
        icon.set_pixel_size(48)
        icon.add_css_class("accent")
        content.append(icon)

        title = Gtk.Label(label=profile.name)
        title.add_css_class("heading")
        content.append(title)

        desc = Gtk.Label(label=profile.description)
        desc.set_wrap(True)
        desc.set_max_width_chars(30)
        desc.set_justify(Gtk.Justification.CENTER)
        desc.add_css_class("dim-label")
        content.append(desc)

        hint = Gtk.Label(label="Click to run this setup")
        hint.add_css_class("caption")
        hint.add_css_class("dim-label")
        hint.set_halign(Gtk.Align.CENTER)
        content.append(hint)
        self.set_child(content)


class WorkstationSystemDashboardPanel(Gtk.Box):
    """The unified workstation dashboard with outcome wizards."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        _margin_all(self, 24)
        
        self._executor = HostExecutor()
        self._installer = PowerInstaller(self._executor)
        self._profile_run_busy = False
        self._stats_alive = True
        self._stats_timer_id: int = 0

        self.build_ui()

    def build_ui(self) -> None:
        # 1. Header
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title = Gtk.Label(label="Power-User System Builder")
        title.set_halign(Gtk.Align.START)
        title.add_css_class("title-1")
        
        subtitle = Gtk.Label(label="Transform your Linux machine into a complete development environment in one click.")
        subtitle.set_halign(Gtk.Align.START)
        subtitle.add_css_class("dim-label")
        
        header.append(title)
        header.append(subtitle)
        self.append(header)

        # 2. Progress Overlay (Hidden by default)
        self._progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._progress_box.set_visible(False)
        self._progress_box.add_css_class("card")
        self._progress_box.set_margin_bottom(12)
        _margin_all(self._progress_box, 18)
        
        self._progress_title = Gtk.Label(label="Current Operation")
        self._progress_title.add_css_class("heading")
        self._progress_title.set_halign(Gtk.Align.START)
        
        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_show_text(True)
        
        self._progress_status = Gtk.Label(label="Initializing...")
        self._progress_status.set_halign(Gtk.Align.START)
        self._progress_status.add_css_class("caption")
        
        self._progress_box.append(self._progress_title)
        self._progress_box.append(self._progress_bar)
        self._progress_box.append(self._progress_status)
        self.append(self._progress_box)

        # 3. Quick Start Wizards
        wizards_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        wizards_label = Gtk.Label(label="Recommended Setups")
        wizards_label.set_halign(Gtk.Align.START)
        wizards_label.set_hexpand(True)
        wizards_label.add_css_class("heading")
        wizards_header.append(wizards_label)
        help_btn = Gtk.Button.new_from_icon_name("help-about-symbolic")
        help_btn.set_valign(Gtk.Align.CENTER)
        help_btn.set_tooltip_text("What outcome profiles do")
        help_btn.add_css_class("flat")
        help_btn.connect("clicked", self._on_wizards_help_clicked)
        wizards_header.append(help_btn)
        self.append(wizards_header)

        self._wizards_flow = Gtk.FlowBox()
        self._wizards_flow.set_valign(Gtk.Align.START)
        self._wizards_flow.set_max_children_per_line(3)
        self._wizards_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._wizards_flow.set_column_spacing(12)
        self._wizards_flow.set_row_spacing(12)
        
        for profile in self._installer.get_profiles():
            card = OutcomeWizardCard(profile)
            card.connect("clicked", self._on_wizard_clicked)
            self._wizards_flow.append(card)

        self.append(self._wizards_flow)

        power_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        power_row.set_margin_top(10)
        self._install_all_btn = Gtk.Button(label="Install all profiles (power mode)…")
        self._install_all_btn.set_tooltip_text(
            "Runs every loaded outcome profile in order. Requires Docker for container steps, "
            "free disk space, and may take a long time."
        )
        self._install_all_btn.connect("clicked", self._on_install_all_clicked)
        power_row.append(self._install_all_btn)
        self.append(power_row)

        # 4. System Health Summary
        health_label = Gtk.Label(label="System Health")
        health_label.set_halign(Gtk.Align.START)
        health_label.set_margin_top(12)
        health_label.add_css_class("heading")
        self.append(health_label)

        self._health_grid = Gtk.Grid()
        self._health_grid.set_column_spacing(12)
        self._health_grid.set_row_spacing(12)
        self._health_grid.set_column_homogeneous(True)
        
        self._cpu_card = self._make_stats_card("CPU Usage", "0%", "system-run-symbolic")
        self._mem_card = self._make_stats_card("Memory", "0 / 0 GiB", "media-flash-symbolic")
        self._disk_card = self._make_stats_card("Disk Space", "checking...", "drive-harddisk-symbolic")
        
        self._health_grid.attach(self._cpu_card, 0, 0, 1, 1)
        self._health_grid.attach(self._mem_card, 1, 0, 1, 1)
        self._health_grid.attach(self._disk_card, 2, 0, 1, 1)
        
        self.append(self._health_grid)

        # Health polling: avoid hammering the host (CPU sample sleeps ~280ms per tick).
        GLib.idle_add(self._stats_idle_first_fetch)
        self._stats_timer_id = GLib.timeout_add_seconds(18, self._update_stats)

    def do_unrealize(self) -> None:
        """Stop periodic host sampling when the panel is destroyed (reduces background load)."""
        self._stats_alive = False
        if self._stats_timer_id:
            GLib.source_remove(self._stats_timer_id)
            self._stats_timer_id = 0
        Gtk.Box.do_unrealize(self)

    def _stats_idle_first_fetch(self) -> bool:
        if self._stats_alive and self.get_mapped():
            self._run_stats_fetch()
        return False

    def _make_stats_card(self, title: str, value: str, icon: str) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.add_css_class("card")
        _margin_all(box, 12)
        
        img = Gtk.Image.new_from_icon_name(icon)
        img.set_pixel_size(24)
        img.add_css_class("dim-label")
        box.append(img)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        t_lbl = Gtk.Label(label=title)
        t_lbl.set_halign(Gtk.Align.START)
        t_lbl.add_css_class("caption")
        t_lbl.add_css_class("dim-label")
        
        v_lbl = Gtk.Label(label=value)
        v_lbl.set_halign(Gtk.Align.START)
        v_lbl.add_css_class("heading")
        
        vbox.append(t_lbl)
        vbox.append(v_lbl)
        box.append(vbox)
        
        # Internal reference for easy updating
        box._value_label = v_lbl
        return box

    def _on_wizard_clicked(self, card: OutcomeWizardCard) -> None:
        if self._profile_run_busy:
            return
        profile = card.profile
        self._profile_run_busy = True
        self._progress_box.set_visible(True)
        self._progress_title.set_label(f"Setting up: {profile.name}")
        self._progress_bar.set_fraction(0.0)
        self._progress_status.set_label("Initializing…")

        self._wizards_flow.set_sensitive(False)
        self._install_all_btn.set_sensitive(False)

        def _on_progress(_name: str, pct: float, status: str) -> None:
            GLib.idle_add(self._progress_bar.set_fraction, min(1.0, max(0.0, pct / 100.0)))
            GLib.idle_add(self._progress_status.set_label, status)

        def _work() -> None:
            async def _run() -> bool:
                return await self._installer.run_profile(profile.id, _on_progress)

            try:
                ok = asyncio.run(_run())
            except Exception:
                log.exception("Outcome profile %s failed", profile.id)
                GLib.idle_add(self._on_install_finished, False)
                return
            GLib.idle_add(self._on_install_finished, ok)

        _bg(_work)

    def _on_wizards_help_clicked(self, _btn: Gtk.Button) -> None:
        root = self.get_root()
        transient = root if isinstance(root, Gtk.Window) else None
        dlg = Adw.MessageDialog(
            transient_for=transient,
            heading="Outcome profiles",
            body=(
                "Each card runs a scripted stack: distro packages, optional global npm tools, "
                "systemd units, Docker containers, and (for AI) model pulls when configured. "
                "Failures are logged; Docker steps need a working engine. "
                "Use power mode only when you intend to install everything in the list."
            ),
        )
        dlg.add_response("close", "OK")
        dlg.set_default_response("close")
        dlg.set_close_response("close")
        dlg.connect("response", lambda d, *_: d.destroy())
        dlg.present()

    def _on_install_all_clicked(self, _btn: Gtk.Button) -> None:
        if self._profile_run_busy:
            return
        root = self.get_root()
        transient = root if isinstance(root, Gtk.Window) else None
        n = len(self._installer.get_profiles())
        dlg = Adw.MessageDialog(
            transient_for=transient,
            heading="Install all outcome profiles?",
            body=(
                f"This will run all {n} loaded profiles in sequence (packages, npm, systemd, Docker, …). "
                "Ensure Docker is available for image steps, you have disk space, and time for installs. "
                "Continue?"
            ),
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("confirm", "Install all")
        dlg.set_response_appearance("confirm", Adw.ResponseAppearance.SUGGESTED)
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")
        dlg.connect("response", self._on_install_all_dialog_response)
        dlg.present()

    def _on_install_all_dialog_response(self, dlg: Adw.MessageDialog, response: str) -> None:
        dlg.destroy()
        if response != "confirm":
            return
        if self._profile_run_busy:
            return
        self._profile_run_busy = True
        self._progress_box.set_visible(True)
        self._progress_title.set_label("Power mode: all profiles")
        self._progress_bar.set_fraction(0.0)
        self._progress_status.set_label("Initializing…")
        self._wizards_flow.set_sensitive(False)
        self._install_all_btn.set_sensitive(False)

        def _on_progress(_name: str, pct: float, status: str) -> None:
            GLib.idle_add(self._progress_bar.set_fraction, min(1.0, max(0.0, pct / 100.0)))
            GLib.idle_add(self._progress_title.set_label, _name)
            GLib.idle_add(self._progress_status.set_label, status)

        def _work() -> None:
            async def _run() -> bool:
                return await self._installer.run_all_profiles(_on_progress)

            try:
                ok = asyncio.run(_run())
            except Exception:
                log.exception("run_all_profiles failed")
                GLib.idle_add(self._on_install_all_finished, False)
                return
            GLib.idle_add(self._on_install_all_finished, ok)

        _bg(_work)

    def _on_install_all_finished(self, success: bool) -> None:
        self._profile_run_busy = False
        self._wizards_flow.set_sensitive(True)
        self._install_all_btn.set_sensitive(True)
        if success:
            self._progress_status.set_label("All profiles finished.")
            emit_utility_toast("Power mode: all profiles completed.", "info", 8)
        else:
            self._progress_status.set_label("Stopped or failed. Check logs.")
            emit_utility_toast("Power mode did not complete successfully.", "error", 10)

    def _on_install_finished(self, success: bool) -> None:
        self._profile_run_busy = False
        self._wizards_flow.set_sensitive(True)
        self._install_all_btn.set_sensitive(True)
        if success:
            self._progress_status.set_label("All systems ready.")
            emit_utility_toast(f"Setup finished: {self._progress_title.get_label()}", "info", 6)
        else:
            self._progress_status.set_label("Setup failed. Check logs.")
            emit_utility_toast("Setup did not complete successfully.", "error", 8)

    def _update_stats(self) -> bool:
        """GLib timeout; return False to stop if panel is gone."""
        if not self._stats_alive:
            return False
        if not self.get_mapped():
            return True
        self._run_stats_fetch()
        return True

    def _run_stats_fetch(self) -> None:
        def _fetch() -> None:
            from ui.widgets.workstation.servers_overview import (
                _host_cpu_pct_between_samples,
                _parse_mem_pct,
            )

            cpu = _host_cpu_pct_between_samples(self._executor)
            _mem_pct, mem_str = _parse_mem_pct(self._executor)

            r = self._executor.run_sync(["df", "-h", "/"], timeout=5)
            disk_str = "Unknown"
            if r.success and len(r.stdout.splitlines()) > 1:
                line = r.stdout.splitlines()[1]
                parts = line.split()
                if len(parts) > 3:
                    disk_str = f"{parts[3]} free / {parts[1]} total"

            GLib.idle_add(self._cpu_card._value_label.set_label, f"{cpu:.1f}%")
            GLib.idle_add(self._mem_card._value_label.set_label, mem_str)
            GLib.idle_add(self._disk_card._value_label.set_label, disk_str)

        _bg(_fetch)
