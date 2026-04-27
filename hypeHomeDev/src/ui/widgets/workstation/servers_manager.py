"""Workstation → Servers: Docker, local runtime, ports, systemd, and cross-links for backend devs."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from ui.widgets.workstation.docker_cheatsheet import DockerCheatsheetPage  # noqa: E402
from ui.widgets.workstation.docker_manager import WorkstationDockerPanel  # noqa: E402
from ui.widgets.workstation.learn_factory import WorkstationLearnFactoryPage  # noqa: E402
from ui.widgets.workstation.nav_helper import navigate_workstation_section  # noqa: E402
from ui.widgets.workstation.servers_overview import WorkstationServersOverviewPanel  # noqa: E402
from ui.widgets.workstation.workstation_utils import _bg, _clear_preferences_group_rows  # noqa: E402

log = logging.getLogger(__name__)

_ROW_LIMIT = 150


def _wrap_learn_page_scroll(inner: Gtk.Widget) -> Gtk.ScrolledWindow:
    """Learn-factory pages are tall; ensure a dedicated viewport under Servers tabs."""
    sw = Gtk.ScrolledWindow(
        hexpand=True,
        vexpand=True,
        hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
    )
    try:
        sw.set_overlay_scrolling(False)
    except (AttributeError, TypeError):
        pass
    sw.set_child(inner)
    return sw
_RUNNING_POLL_SECONDS = 8


_SYSTEMCTL_JSON = [
    "systemctl",
    "list-units",
    "--type=service",
    "--state=running",
    "--no-pager",
    "--no-legend",
    "-o",
    "json",
]
_SYSTEMCTL_TABLE = [
    "systemctl",
    "list-units",
    "--type=service",
    "--state=running",
    "--no-pager",
    "--no-legend",
]
_SYSTEMCTL_USER_JSON = [
    "systemctl",
    "--user",
    "list-units",
    "--type=service",
    "--state=running",
    "--no-pager",
    "--no-legend",
    "-o",
    "json",
]
_SYSTEMCTL_USER_TABLE = [
    "systemctl",
    "--user",
    "list-units",
    "--type=service",
    "--state=running",
    "--no-pager",
    "--no-legend",
]
_DOCKER_PS = ["docker", "ps", "--format", "{{.Names}}\t{{.Image}}\t{{.Status}}"]


def _parse_systemctl_json(stdout: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return rows
    if not isinstance(data, list):
        return rows
    for item in data:
        if not isinstance(item, dict):
            continue
        unit = str(item.get("unit") or item.get("name") or "").strip()
        if not unit.endswith(".service"):
            continue
        desc = str(item.get("description") or "").strip() or "—"
        rows.append((unit, desc))
    rows.sort(key=lambda x: x[0].lower())
    return rows


def _parse_systemctl_table(stdout: str) -> list[tuple[str, str]]:
    """Fallback when ``systemctl -o json`` is unavailable."""
    rows: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("UNIT "):
            continue
        m = re.match(
            r"^(?P<u>\S+\.service)\s+\S+\s+\S+\s+\S+\s+(?P<desc>.+)$",
            line,
        )
        if m:
            rows.append((m.group("u"), m.group("desc").strip()))
    rows.sort(key=lambda x: x[0].lower())
    return rows


def _fetch_running_services(ex: HostExecutor, *, user_scope: bool) -> list[tuple[str, str]]:
    cmd = _SYSTEMCTL_USER_JSON if user_scope else _SYSTEMCTL_JSON
    r = ex.run_sync(cmd, timeout=90.0)
    if r.success and r.stdout.strip():
        parsed = _parse_systemctl_json(r.stdout)
        if parsed:
            return parsed
    cmd_t = _SYSTEMCTL_USER_TABLE if user_scope else _SYSTEMCTL_TABLE
    r2 = ex.run_sync(cmd_t, timeout=90.0)
    if not r2.success or not r2.stdout.strip():
        return []
    return _parse_systemctl_table(r2.stdout)


def _fetch_running_docker(ex: HostExecutor) -> list[tuple[str, str, str]]:
    r = ex.run_sync(_DOCKER_PS, timeout=60.0)
    if not r.success or not r.stdout.strip():
        return []
    out: list[tuple[str, str, str]] = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            out.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
        elif len(parts) == 2:
            out.append((parts[0].strip(), parts[1].strip(), ""))
        elif len(parts) == 1 and parts[0].strip():
            out.append((parts[0].strip(), "", ""))
    out.sort(key=lambda x: x[0].lower())
    return out


class WorkstationServersHubPanel(Gtk.Box):
    """Overview: what Servers covers + one-click jumps and links to related Workstation areas."""

    def __init__(self, *, on_open_tab: Callable[[str], None], **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
            hexpand=True,
        )
        try:
            scroll.set_overlay_scrolling(False)
        except (AttributeError, TypeError):
            pass
        page = Adw.PreferencesPage()

        intro = Adw.PreferencesGroup(
            title="At a glance",
            description=(
                "Servers: monitor-style Overview, lists, Docker, plus links to SSH, VPN, and AI tools."
            ),
        )
        page.add(intro)

        jump = Adw.PreferencesGroup(
            title="Jump to",
            description="Open a tab in this Servers section.",
        )
        for title, subtitle, tab in (
            (
                "Overview",
                "Monitor-style dashboard: load, top CPU/memory, host table.",
                "overview",
            ),
            (
                "Running",
                "Active systemd services and Docker containers on this machine.",
                "running",
            ),
            (
                "Docker Docs",
                "Commands, compose patterns, and troubleshooting next to Docker tooling.",
                "docs",
            ),
            (
                "Docker",
                "Install engine, run containers, images, volumes, networks, cleanup.",
                "docker",
            ),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            btn = Gtk.Button(label="Open")
            btn.add_css_class("suggested-action")
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect("clicked", lambda *_b, t=tab: on_open_tab(t))
            row.add_suffix(btn)
            jump.add(row)
        page.add(jump)

        related = Adw.PreferencesGroup(
            title="Related elsewhere",
            description="Other Workstation areas that pair with local servers.",
        )
        for title, subtitle, target in (
            (
                "SSH identity",
                "Keys, ssh-keygen, GitHub host test — under Config.",
                "config:ssh",
            ),
            (
                "VPN and sync",
                "Tailscale, Dropbox, NordVPN, … — under Services.",
                "services",
            ),
            (
                "AI runtimes",
                "Ollama, LM Studio, Open WebUI — under AI Tools.",
                "ai",
            ),
        ):
            row = Adw.ActionRow(title=title, subtitle=subtitle)
            btn = Gtk.Button(label="Go")
            btn.set_valign(Gtk.Align.CENTER)
            btn.connect(
                "clicked",
                lambda *_b, tid=target: self._on_go_elsewhere(tid),
            )
            row.add_suffix(btn)
            related.add(row)
        page.add(related)

        scroll.set_child(page)
        self.append(scroll)

    @staticmethod
    def _on_go_elsewhere(target: str) -> None:
        if not navigate_workstation_section(target):
            log.warning("WorkstationServersHubPanel: navigation failed for %r", target)

    def reset_subsections(self) -> None:
        pass


class WorkstationServersRunningPanel(Gtk.Box):
    """Live list of running systemd services (system and user) and ``docker ps``."""

    def __init__(self, *, parent_stack: Gtk.Stack, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self._parent_stack = parent_stack
        self._busy = False
        self._poll_id = 0

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        toolbar.set_margin_start(18)
        toolbar.set_margin_end(18)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)

        self._refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self._refresh_btn.set_tooltip_text("Refresh lists")
        self._refresh_btn.connect("clicked", lambda *_: self.refresh())
        toolbar.append(self._refresh_btn)

        self._status = Gtk.Label(label="Open this tab to load running services.")
        self._status.add_css_class("dim-label")
        self._status.set_hexpand(True)
        self._status.set_xalign(0.0)
        toolbar.append(self._status)

        self.append(toolbar)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
            hexpand=True,
        )
        try:
            scroll.set_overlay_scrolling(False)
        except (AttributeError, TypeError):
            pass
        self._page = Adw.PreferencesPage()
        self._page.set_vexpand(False)

        self._sys_group = Adw.PreferencesGroup(
            title="System services",
            description="Units reported as active by systemctl (system scope).",
        )
        self._page.add(self._sys_group)

        self._user_group = Adw.PreferencesGroup(
            title="User session services",
            description="systemctl --user; empty if no user session manager.",
        )
        self._page.add(self._user_group)

        self._docker_group = Adw.PreferencesGroup(
            title="Docker containers",
            description="Output of docker ps (running only).",
        )
        self._page.add(self._docker_group)

        scroll.set_child(self._page)
        self.append(scroll)

        self._visibility_handler = self._parent_stack.connect(
            "notify::visible-child", self._on_stack_visible_child
        )

    def do_unrealize(self) -> None:
        self._stop_poll()
        if getattr(self, "_visibility_handler", 0):
            self._parent_stack.disconnect(self._visibility_handler)
            self._visibility_handler = 0
        Gtk.Box.do_unrealize(self)

    def _on_stack_visible_child(self, stack: Gtk.Stack, *_args: Any) -> None:
        if stack.get_visible_child() == self:
            self.refresh()
            self._start_poll()
        else:
            self._stop_poll()

    def _start_poll(self) -> None:
        if self._poll_id:
            return
        self._poll_id = GLib.timeout_add_seconds(_RUNNING_POLL_SECONDS, self._on_poll_tick)

    def _stop_poll(self) -> None:
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = 0

    def _on_poll_tick(self) -> bool:
        if self._parent_stack.get_visible_child() is not self:
            self._poll_id = 0
            return False
        if not self._busy:
            self.refresh()
        return True

    def refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        self._status.set_label("Refreshing…")
        self._refresh_btn.set_sensitive(False)

        def work() -> None:
            ex = HostExecutor()
            system = _fetch_running_services(ex, user_scope=False)
            user = _fetch_running_services(ex, user_scope=True)
            docker = _fetch_running_docker(ex)
            GLib.idle_add(self._apply_results, system, user, docker)

        _bg(work)

    def _apply_results(
        self,
        system: list[tuple[str, str]],
        user: list[tuple[str, str]],
        docker: list[tuple[str, str, str]],
    ) -> bool:
        self._busy = False
        self._refresh_btn.set_sensitive(True)

        def cap(rows: list[Any]) -> tuple[list[Any], int]:
            if len(rows) <= _ROW_LIMIT:
                return rows, 0
            return rows[:_ROW_LIMIT], len(rows) - _ROW_LIMIT

        sys_rows, sys_extra = cap(system)
        user_rows, user_extra = cap(user)
        dock_rows, dock_extra = cap(docker)

        self._fill_unit_group(self._sys_group, sys_rows, sys_extra, "No active system services.")
        self._fill_unit_group(self._user_group, user_rows, user_extra, "No active user services.")
        self._fill_docker_group(dock_rows, dock_extra)

        total = len(system) + len(user) + len(docker)
        extra_note = ""
        if sys_extra + user_extra + dock_extra > 0:
            extra_note = f" (lists capped; {_ROW_LIMIT} rows max per section)"
        poll_note = f" · auto-refresh every {_RUNNING_POLL_SECONDS}s while this tab is open"
        self._status.set_label(f"Updated — {total} entries total.{extra_note}{poll_note}")
        return False

    def _fill_unit_group(
        self,
        group: Adw.PreferencesGroup,
        rows: list[tuple[str, str]],
        extra: int,
        empty_msg: str,
    ) -> None:
        _clear_preferences_group_rows(group)
        if not rows:
            row = Adw.ActionRow(title=empty_msg, subtitle="")
            group.add(row)
        else:
            for unit, desc in rows:
                group.add(Adw.ActionRow(title=unit, subtitle=desc))
        if extra > 0:
            group.add(
                Adw.ActionRow(
                    title=f"… and {extra} more",
                    subtitle=f"Showing first {_ROW_LIMIT} only.",
                ),
            )

    def _fill_docker_group(
        self,
        rows: list[tuple[str, str, str]],
        extra: int,
    ) -> None:
        _clear_preferences_group_rows(self._docker_group)
        if not rows:
            self._docker_group.add(
                Adw.ActionRow(
                    title="No running containers",
                    subtitle="Install Docker or start a container, then refresh.",
                ),
            )
        else:
            for name, image, status in rows:
                sub = " — ".join(p for p in (image, status) if p)
                self._docker_group.add(Adw.ActionRow(title=name, subtitle=sub or "—"))
        if extra > 0:
            self._docker_group.add(
                Adw.ActionRow(
                    title=f"… and {extra} more",
                    subtitle=f"Showing first {_ROW_LIMIT} only.",
                ),
            )

    def reset_subsections(self) -> None:
        self._stop_poll()


_SERVER_TABS: list[tuple[str, str, type]] = [
    ("overview", "Overview", WorkstationServersOverviewPanel),
    ("hub", "Guide", WorkstationServersHubPanel),
    ("running", "Running", WorkstationServersRunningPanel),
    ("docs", "Docker Docs", DockerCheatsheetPage),
    ("docker", "Docker", WorkstationDockerPanel),
]


class WorkstationServersPanel(Gtk.Box):
    """Top-level Servers panel: Overview | Hub | Running | Docker Docs | Docker."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self.set_hexpand(True)
        self.set_vexpand(True)

        self._stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.SLIDE_LEFT_RIGHT,
            transition_duration=180,
            hexpand=True,
            vexpand=True,
        )

        switcher = Gtk.StackSwitcher()
        switcher.set_stack(self._stack)
        switcher.set_margin_top(6)
        switcher.set_margin_bottom(4)
        switcher.set_margin_start(16)
        switcher.set_margin_end(16)
        switcher.set_halign(Gtk.Align.CENTER)
        switcher.add_css_class("workstation-subsection-switcher")

        self._children: list[Gtk.Widget] = []
        for sid, title, cls in _SERVER_TABS:
            if cls is WorkstationServersHubPanel:
                child = cls(on_open_tab=self._stack.set_visible_child_name)
            elif cls in (
                WorkstationServersOverviewPanel,
                WorkstationServersRunningPanel,
            ):
                child = cls(parent_stack=self._stack)
            else:
                raw = cls()
                if isinstance(raw, WorkstationLearnFactoryPage):
                    child = _wrap_learn_page_scroll(raw)
                else:
                    child = raw
            self._children.append(child)
            self._stack.add_titled(child, sid, title)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        self.append(switcher)
        self.append(sep)
        self.append(self._stack)

    def goto_subsection(self, sub_id: str) -> bool:
        """Deep-link from :meth:`WorkstationPage.goto_section` (``servers:running``, …)."""
        child = self._stack.get_child_by_name(sub_id)
        if child is None:
            return False
        self._stack.set_visible_child_name(sub_id)
        return True

    def reset_subsections(self) -> None:
        self._stack.set_visible_child_name("overview")
        for child in self._children:
            reset = getattr(child, "reset_subsections", None)
            if callable(reset):
                reset()
