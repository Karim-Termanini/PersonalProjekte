"""HypeDevHome — Environments overview stub for Utilities (Phase 5).

Full container creation lives under Machine Setup; this view surfaces detection only.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.environments import EnvironmentManager  # noqa: E402
from core.setup.host_executor import HostExecutor  # noqa: E402

log = logging.getLogger(__name__)


class UtilitiesEnvironments(Gtk.Box):
    """Shows container tool detection and points users to Machine Setup."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._executor = HostExecutor()
        self._env = EnvironmentManager(self._executor)
        self._build_ui()
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            cast(Any, app).enqueue_task(self._detect())

    def _build_ui(self) -> None:
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="Development environments",
            description=(
                "Distrobox, Toolbx, Docker, and Podman are detected here. "
                "Use Machine Setup → Environments for templates, stacks, and sync."
            ),
        )
        self._status_label = Gtk.Label(label="Detecting…")
        self._status_label.set_margin_start(12)
        self._status_label.set_margin_end(12)
        self._status_label.set_margin_bottom(8)
        self._status_label.set_xalign(0)
        self._status_label.add_css_class("dim-label")
        self._status_label.set_wrap(True)
        group.add(self._status_label)
        page.add(group)
        scroll.set_child(page)
        self.append(scroll)

    async def _detect(self) -> None:
        await self._env.initialize()
        parts = [
            f"Distrobox: {'yes' if self._env.has_distrobox else 'no'}",
            f"Toolbx: {'yes' if self._env.has_toolbx else 'no'}",
            f"Podman: {'yes' if self._env.has_podman else 'no'}",
            f"Docker: {'yes' if self._env.has_docker else 'no'}",
            f"devcontainer CLI: {'yes' if self._env.has_devcontainer_cli else 'no'}",
        ]
        lines = " · ".join(parts)
        GLib.idle_add(self._status_label.set_label, lines)
