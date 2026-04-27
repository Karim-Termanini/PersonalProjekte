"""HypeDevHome — System information panel for Utilities (Phase 5)."""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

log = logging.getLogger(__name__)


class UtilitiesSystemInfo(Gtk.Box):
    """Read-only OS and hardware summary."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._build_ui()
        GLib.idle_add(self._populate)

    def _build_ui(self) -> None:
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        page = Adw.PreferencesPage()
        self._os_group = Adw.PreferencesGroup(
            title="Operating system",
            description="From /etc/os-release and the running kernel",
        )
        self._hw_group = Adw.PreferencesGroup(
            title="Hardware and memory",
            description="Snapshot from this process (psutil when available)",
        )
        page.add(self._os_group)
        page.add(self._hw_group)
        scroll.set_child(page)
        self.append(scroll)

    def _populate(self) -> bool:
        self._add_row(self._os_group, "Python", f"{sys.version.split()[0]} — {sys.executable}")
        self._add_row(self._os_group, "Platform", platform.platform())

        os_release = Path("/etc/os-release")
        if os_release.is_file():
            try:
                txt = os_release.read_text(encoding="utf-8", errors="replace")
                pretty = ""
                for line in txt.splitlines():
                    if line.startswith("PRETTY_NAME="):
                        pretty = line.split("=", 1)[-1].strip().strip('"')
                        break
                if pretty:
                    self._add_row(self._os_group, "Distribution", pretty)
            except OSError as e:
                log.debug("os-release: %s", e)

        try:
            import psutil

            vm = psutil.virtual_memory()
            self._add_row(
                self._hw_group,
                "Memory",
                f"{vm.percent:.0f}% used — "
                f"{vm.available / (1024**3):.1f} GiB available of {vm.total / (1024**3):.1f} GiB",
            )
            du = psutil.disk_usage("/")
            self._add_row(
                self._hw_group,
                "Root filesystem",
                f"{du.percent:.0f}% used — {du.free / (1024**3):.1f} GiB free of {du.total / (1024**3):.1f} GiB",
            )
            cpus = psutil.cpu_count(logical=True) or 0
            phys = psutil.cpu_count(logical=False) or 0
            self._add_row(self._hw_group, "CPU", f"{cpus} logical cores ({phys} physical)")
        except Exception as e:
            self._add_row(self._hw_group, "Details", f"Limited: {e}")

        return False

    def _add_row(self, group: Adw.PreferencesGroup, title: str, subtitle: str) -> None:
        row = Adw.ActionRow(title=title, subtitle=subtitle)
        row.set_subtitle_selectable(True)
        group.add(row)
