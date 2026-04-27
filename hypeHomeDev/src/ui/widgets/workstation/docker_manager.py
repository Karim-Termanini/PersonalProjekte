"""Workstation → Docker: install, containers, images, volumes, networks, config."""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, ClassVar

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.package_installer import PackageInstaller  # noqa: E402
from core.setup.systemd_manager import SystemdManager  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.subsection_bar import WorkstationSubsectionBar  # noqa: E402
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    _SHELL_PREAMBLE,
    _bg,
    _clear_preferences_group_rows,
    _copy,
    _run_cmd,
)
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    PACKAGE_MANAGER as _PKG_MANAGER,
)

log = logging.getLogger(__name__)

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")
_LOG_LEVEL_RE = re.compile(r"\b(DEBUG|INFO|WARN|ERROR|TRACE)\b")


_TERMINAL_CANDIDATES = [
    "ghostty", "kitty", "alacritty", "wezterm", "gnome-terminal",
    "konsole", "xfce4-terminal", "tilix", "xterm",
]


def _find_terminal() -> str | None:
    """Return the first available terminal emulator binary name."""
    import shutil
    for t in _TERMINAL_CANDIDATES:
        if shutil.which(t):
            return t
    return None


def _command_needs_real_terminal(cmd: str) -> bool:
    """True if the command must run in a real TTY (sudo password, pipe-to-shell, etc.).

    InstallDialog uses piped subprocess — no TTY — so sudo cannot prompt and many
    installers that call sudo internally will hang or fail silently.
    """
    c = cmd.strip()
    if not c:
        return False
    # Privilege / auth
    if re.search(r"\bsudo\b", c):
        return True
    if re.search(r"\bpkexec\b", c):
        return True
    if re.search(r"\bdoas\b", c):
        return True
    if re.search(r"\bsu\s+-c\b", c) or re.search(r"\bsu\s+-l\b", c):
        return True
    # Often interactive (password / shell change)
    if re.search(r"\bchsh\b", c):
        return True
    if re.search(r"\bpasswd\b", c):
        return True
    # Remote curl / wget installers that run scripts (often prompt or sudo inside)
    if re.search(r"\|\s*(ba)?sh\b", c):
        return True
    return bool(re.search(r"install\.sh", c, re.I))


def _open_terminal_run_command(cmd_str: str) -> None:
    """Run *cmd_str* in a new terminal with login-shell env and a clear pause at the end.

    Like a Windows installer window: you see all output and can type passwords when asked.
    """
    try:
        fd, path = tempfile.mkstemp(prefix="hypehome-run-", suffix=".sh", text=True)
        with os.fdopen(fd, "w") as f:
            f.write("#!/usr/bin/env bash\n")
            f.write("set +e\n")
            f.write(_SHELL_PREAMBLE)
            f.write(
                'printf "\\n\\033[1;36m=== HypeHome — running command '
                '(password prompts appear below) ===\\033[0m\\n\\n"\n'
            )
            f.write(cmd_str)
            if not cmd_str.endswith("\n"):
                f.write("\n")
            f.write('EC=$?\n')
            f.write('printf "\\n\\033[1;36m=== Exit code: %s ===\\033[0m\\n" "$EC"\n')
            f.write('read -r -p "Press Enter to close this window..."\n')
            f.write(f'rm -f "{path}"\n')
        os.chmod(path, 0o755)
    except OSError as exc:
        log.warning("Failed to write temp script: %s", exc)
        emit_utility_toast("Could not prepare run script.", "error")
        return

    _open_in_terminal(f"/bin/bash {path}")


def _open_in_terminal(cmd: str) -> None:
    """Open *cmd* in a real terminal window (needed for TUI apps like vim)."""
    term = _find_terminal()
    if term is None:
        emit_utility_toast("No terminal emulator found.", "error")
        return

    if term in ("ghostty", "kitty", "alacritty", "wezterm", "konsole"):
        args = [term, "-e", "bash", "-c", cmd]
    elif term == "gnome-terminal":
        args = [term, "--", "bash", "-c", cmd]
    else:
        args = [term, "-e", f"bash -c '{cmd}'"]

    try:
        subprocess.Popen(args, start_new_session=True)
    except Exception as exc:
        log.warning("Failed to open terminal: %s", exc)
        emit_utility_toast(f"Could not open terminal: {exc}", "error")


def _run_shell(cmd_str: str, *, root: bool = False, timeout: float = 120) -> None:
    """Run a shell command in a background thread; toast result on GTK main thread."""
    def _work() -> None:
        shell_cmd = cmd_str
        if root and not cmd_str.startswith("sudo "):
            shell_cmd = f"sudo {cmd_str}"
        GLib.idle_add(emit_utility_toast, f"Running: {shell_cmd}", "info", 3)
        try:
            r = subprocess.run(
                shell_cmd, shell=True, capture_output=True, text=True, timeout=timeout,
            )
            ok = r.returncode == 0
            out = (r.stdout.strip() or r.stderr.strip())[:200]
            msg = f"{'Done' if ok else 'Failed'}: {out or shell_cmd}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 8)
        except Exception as e:
            GLib.idle_add(emit_utility_toast, f"Error: {e}", "error", 8)

    _bg(_work)


# ── Visible install dialog ───────────────────────────────────


class InstallDialog(Adw.Dialog):
    """Windows-style install dialog: shows live command output in a scrollable view."""

    def __init__(
        self,
        cmd_str: str,
        title: str = "Installing…",
        on_finished: Any = None,
    ) -> None:
        super().__init__()
        self.set_title(title)
        self.set_content_width(700)
        self.set_content_height(460)

        self._cmd = cmd_str
        self._process: subprocess.Popen[str] | None = None
        self._finished = False
        self._on_finished = on_finished

        header = Adw.HeaderBar()

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._status_label = Gtk.Label(label="Running…")
        self._status_label.add_css_class("caption")
        self._status_label.add_css_class("dim-label")
        toolbar.append(self._status_label)

        copy_btn = Gtk.Button(label="Copy output")
        copy_btn.set_tooltip_text("Copy full output to clipboard")
        copy_btn.connect("clicked", self._on_copy)
        toolbar.append(copy_btn)

        header.pack_start(toolbar)

        # Command label
        cmd_label = Gtk.Label(label=cmd_str, xalign=0.0, selectable=True, wrap=True)
        cmd_label.add_css_class("monospace")
        cmd_label.add_css_class("dim-label")
        cmd_label.set_margin_start(12)
        cmd_label.set_margin_end(12)
        cmd_label.set_margin_top(6)
        cmd_label.set_margin_bottom(2)

        hint = Gtk.Label(
            label=(
                "Commands that need a password (sudo) or run a remote installer (| sh) "
                "open in a separate terminal window instead — you type there."
            ),
            xalign=0.0,
            wrap=True,
        )
        hint.add_css_class("caption")
        hint.add_css_class("dim-label")
        hint.set_margin_start(12)
        hint.set_margin_end(12)
        hint.set_margin_bottom(4)

        # Spinner / progress
        self._spinner = Gtk.Spinner()
        self._spinner.start()
        self._spinner.set_margin_start(12)
        self._spinner.set_margin_top(4)
        self._spinner.set_margin_bottom(4)
        self._spinner.set_halign(Gtk.Align.START)

        # Text view for live output
        self._textview = Gtk.TextView()
        self._textview.set_editable(False)
        self._textview.set_cursor_visible(False)
        self._textview.set_monospace(True)
        self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._textview.set_top_margin(8)
        self._textview.set_bottom_margin(8)
        self._textview.set_left_margin(10)
        self._textview.set_right_margin(10)
        self._buffer = self._textview.get_buffer()

        # Backend uses logback %highlight/%cyan in dev profile, which emits ANSI
        # escape sequences. The UI doesn't interpret them, so we strip ANSI and
        # re-apply colors via GTK text tags.
        self._tag_error = self._buffer.create_tag("log_error", foreground="#ef4444")
        self._tag_warn = self._buffer.create_tag("log_warn", foreground="#f59e0b")
        self._tag_info = self._buffer.create_tag("log_info", foreground="#60a5fa")
        self._tag_debug = self._buffer.create_tag("log_debug", foreground="#94a3b8")
        self._tag_trace = self._buffer.create_tag("log_trace", foreground="#a78bfa")

        scroll = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_child(self._textview)
        self._scroll = scroll

        # Result bar
        self._result_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._result_bar.set_margin_start(12)
        self._result_bar.set_margin_end(12)
        self._result_bar.set_margin_top(4)
        self._result_bar.set_margin_bottom(8)
        self._result_icon = Gtk.Image()
        self._result_icon.set_valign(Gtk.Align.CENTER)
        self._result_label = Gtk.Label(xalign=0.0)
        self._result_label.set_hexpand(True)
        self._result_bar.append(self._result_icon)
        self._result_bar.append(self._result_label)
        self._result_bar.set_visible(False)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(header)
        content.append(cmd_label)
        content.append(hint)
        content.append(self._spinner)
        content.append(scroll)
        content.append(self._result_bar)
        self.set_child(content)

        self.connect("closed", self._on_closed)
        _bg(self._execute)

    def _execute(self) -> None:
        try:
            self._process = subprocess.Popen(
                self._cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except Exception as e:
            GLib.idle_add(self._append, f"Error starting command: {e}\n")
            GLib.idle_add(self._mark_done, False)
            return

        for line in iter(self._process.stdout.readline, ""):
            if self._process is None:
                break
            GLib.idle_add(self._append, line)

        if self._process is not None:
            try:
                rc = self._process.wait()
                GLib.idle_add(self._mark_done, rc == 0)
            except Exception as e:
                # UI ARTIFACT FIX: Finding 10 - Capture and log swallowed exceptions
                log.exception("InstallDialog execution error")
                GLib.idle_add(self._append, f"\nError waiting for process: {e}\n")
                GLib.idle_add(self._mark_done, False)

    def _append(self, text: str) -> None:
        if not text:
            return

        # UI ARTIFACT FIX: Finding 13 - stripping ANSI and applying GTK text tags for readability
        clean_text = _ANSI_ESCAPE_RE.sub("", text)

        end = self._buffer.get_end_iter()
        start_offset = end.get_offset()
        self._buffer.insert(end, clean_text)

        # Apply tags based on keywords
        new_start = self._buffer.get_iter_at_offset(start_offset)
        new_end = self._buffer.get_end_iter()

        # Regex-based scanning for more accurate level highlighting
        line_text = clean_text.upper()
        if _LOG_LEVEL_RE.search(line_text):
            m = _LOG_LEVEL_RE.search(line_text)
            if m:
                lvl = m.group(1)
                tag = {
                    "ERROR": self._tag_error,
                    "WARN": self._tag_warn,
                    "INFO": self._tag_info,
                    "DEBUG": self._tag_debug,
                    "TRACE": self._tag_trace,
                }.get(lvl)
                if tag:
                    self._buffer.apply_tag(tag, new_start, new_end)
        elif "FAILED" in line_text or "FATAL" in line_text:
            self._buffer.apply_tag(self._tag_error, new_start, new_end)
        elif "WARNING" in line_text:
            self._buffer.apply_tag(self._tag_warn, new_start, new_end)
        elif "SUCCESS" in line_text or "COMPLETED" in line_text:
            self._buffer.apply_tag(self._tag_info, new_start, new_end)

        mark = self._buffer.create_mark(None, self._buffer.get_end_iter(), False)
        self._textview.scroll_mark_onscreen(mark)
        self._buffer.delete_mark(mark)

    def _mark_done(self, success: bool) -> None:
        self._finished = True
        self._spinner.stop()
        self._spinner.set_visible(False)

        self._result_bar.set_visible(True)
        if success:
            self.set_title("Done")
            self._status_label.set_label("Completed")
            self._result_icon.set_from_icon_name("emblem-ok-symbolic")
            self._result_label.set_label("Command completed successfully.")
            self._result_label.add_css_class("success")
        else:
            self.set_title("Failed")
            self._status_label.set_label("Failed")
            self._result_icon.set_from_icon_name("dialog-error-symbolic")
            self._result_label.set_label("Command exited with an error.")
            self._result_label.add_css_class("error")

        self._append(f"\n{'─' * 40}\n{'✓ Done' if success else '✗ Failed'}\n")

        if self._on_finished:
            self._on_finished(success)

    def _on_copy(self, _btn: Gtk.Button) -> None:
        text = self._buffer.get_text(
            self._buffer.get_start_iter(), self._buffer.get_end_iter(), False,
        )
        _copy(text[:50000])

    def _on_closed(self, _dialog: Adw.Dialog) -> None:
        if self._process and not self._finished:
            with contextlib.suppress(OSError):
                self._process.kill()
            self._process = None


def _run_shell_visible(
    cmd_str: str, widget: Gtk.Widget, *, on_finished: Any = None
) -> None:
    """Run *cmd_str* with visible output: in-app dialog, or a real terminal when a TTY is required.

    sudo / pipe-to-shell installers cannot use the in-app dialog (no TTY for password prompts).
    """
    if _command_needs_real_terminal(cmd_str):
        emit_utility_toast(
            "Opened in a terminal window — watch output there and enter your password when asked.",
            "info",
            8,
        )
        _open_terminal_run_command(cmd_str)
        # on_finished skipped: external terminal; revisit page to refresh status.
        return

    short = cmd_str.split("|")[0].strip().split("/")[-1][:40]
    dialog = InstallDialog(cmd_str, title=f"Installing: {short}", on_finished=on_finished)
    root = widget.get_root()
    if root and isinstance(root, Gtk.Window):
        dialog.present(root)
    else:
        dialog.present(widget)


def docker_container_status(name: str, *, timeout: float = 5) -> str:
    """Return docker inspect State.Status for *name*, or empty string if missing / error."""
    ok, out, _ = _run_cmd(
        ["docker", "inspect", "-f", "{{.State.Status}}", name],
        timeout=timeout,
    )
    return out.strip() if ok else ""


def docker_container_start(name: str, *, timeout: float = 120) -> bool:
    ok, _, _ = _run_cmd(["docker", "start", name], timeout=timeout)
    return ok


def docker_container_stop(name: str, *, timeout: float = 120) -> bool:
    ok, _, _ = _run_cmd(["docker", "stop", name], timeout=timeout)
    return ok


def _docker_catalog_service() -> dict[str, Any]:
    """Return the ``docker`` entry from ``data/services.json`` (shared with Services hub)."""
    path = Path(__file__).resolve().parent / "data" / "services.json"
    fallback: dict[str, Any] = {
        "id": "docker",
        "name": "Docker",
        "unit": "docker.service",
        "binary": "docker",
        "package_name": "docker",
        "description": {"en": "Container runtime and tooling. Requires docker daemon service."},
    }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        log.exception("docker_manager: could not read %s", path)
        return fallback
    for e in data.get("services") or []:
        if isinstance(e, dict) and str(e.get("id", "")) == "docker":
            from ui.widgets.workstation.service_manager import _sanitize_process_service_entry

            return _sanitize_process_service_entry(e)
    return fallback


def _make_docker_service_factory_row() -> Gtk.Widget:
    """Build :class:`ServiceFactoryRow` lazily to avoid ``docker_manager`` ↔ ``service_manager`` import cycle."""
    from ui.widgets.workstation.service_manager import ServiceFactoryRow

    executor = HostExecutor()
    installer = PackageInstaller(executor)
    systemd = SystemdManager()
    return ServiceFactoryRow(
        _docker_catalog_service(),
        systemd=systemd,
        installer=installer,
        executor=executor,
    )


# ── Install page ────────────────────────────────────────────


class _DockerInstallPage(Gtk.Box):
    """Check Docker status and offer install commands — auto-detects distro."""

    _INSTALL_CMDS: ClassVar[dict[str, tuple[str, str]]] = {
        "dnf": ("Fedora / RHEL", "sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin"),
        "apt": ("Ubuntu / Debian", "sudo apt install -y docker.io docker-compose-v2"),
        "pacman": ("Arch", "sudo pacman -S --noconfirm docker docker-compose"),
        "zypper": ("openSUSE", "sudo zypper install -y docker docker-compose"),
        "apk": ("Alpine", "sudo apk add docker docker-compose"),
    }
    _FALLBACK_CMD: ClassVar[tuple[str, str]] = (
        "Official script (any distro)",
        "curl -fsSL https://get.docker.com | sh",
    )

    _POST_CMDS: ClassVar[list[tuple[str, str, bool]]] = [
        ("Add user to docker group", "sudo usermod -aG docker $USER", False),
        ("Verify install", "docker run hello-world", False),
    ]

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        # Status
        self._status_group = Adw.PreferencesGroup(
            title="Docker Status",
            description="Checks whether Docker and Docker Compose are available on this system.",
        )
        self._status_row = Adw.ActionRow(title="Docker Engine", subtitle="Checking…")
        self._compose_row = Adw.ActionRow(title="Docker Compose", subtitle="Checking…")
        self._status_group.add(self._status_row)
        self._status_group.add(self._compose_row)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_valign(Gtk.Align.CENTER)
        refresh_btn.set_tooltip_text("Re-check Docker status")
        refresh_btn.connect("clicked", lambda _b: self._check_status())
        self._status_row.add_suffix(refresh_btn)

        self._svc_row = _make_docker_service_factory_row()
        self._status_group.add(self._svc_row)
        self.append(self._status_group)

        # Install — pick command for detected distro, show others as fallback
        pm = _PKG_MANAGER
        primary = self._INSTALL_CMDS.get(pm)
        if primary:
            label, cmd = primary
            main_group = Adw.PreferencesGroup(
                title=f"Install Docker ({label})",
                description=f"Detected package manager: {pm}. Click Run to install.",
            )
            self._add_run_row(main_group, label, cmd, primary=True)
            self.append(main_group)

            others = [
                (title, c)
                for k, (title, c) in self._INSTALL_CMDS.items()
                if k != pm
            ]
            others.append(self._FALLBACK_CMD)
            other_group = Adw.PreferencesGroup(
                title="Other distributions",
                description="Use these if the auto-detected command is wrong.",
            )
            for ol, oc in others:
                self._add_run_row(other_group, ol, oc)
            self.append(other_group)
        else:
            install_group = Adw.PreferencesGroup(
                title="Install Docker",
                description="Could not detect distro. Pick the right command for your system.",
            )
            for _k, (title, c) in self._INSTALL_CMDS.items():
                self._add_run_row(install_group, title, c)
            self._add_run_row(install_group, *self._FALLBACK_CMD)
            self.append(install_group)

        # Post-install
        post_group = Adw.PreferencesGroup(
            title="Post-install",
            description="Common steps after installing Docker. Click Run to execute.",
        )
        for label, cmd, _needs_root in self._POST_CMDS:
            self._add_run_row(post_group, label, cmd)
        self.append(post_group)

        GLib.idle_add(self._check_status)

    def _add_run_row(self, group: Adw.PreferencesGroup, label: str, cmd: str, *, primary: bool = False) -> None:
        row = Adw.ActionRow(title=label, subtitle=cmd)
        row.set_activatable(True)

        def _on_run(*_args: Any) -> None:
            if primary:
                self._run_primary_docker_install(cmd)
            else:
                _run_shell(cmd)

        row.connect("activated", _on_run)

        run_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
        run_btn.set_valign(Gtk.Align.CENTER)
        run_btn.set_tooltip_text("Run this command")
        run_btn.add_css_class("suggested-action")
        run_btn.connect("clicked", _on_run)
        row.add_suffix(run_btn)

        copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
        copy_btn.set_valign(Gtk.Align.CENTER)
        copy_btn.set_has_frame(False)
        copy_btn.add_css_class("flat")
        copy_btn.set_tooltip_text("Copy command")
        copy_btn.connect("clicked", lambda _b, c=cmd: _copy(c))
        row.add_suffix(copy_btn)

        group.add(row)

    def _check_status(self) -> None:
        def _work() -> None:
            ok, out, _err = _run_cmd(["docker", "--version"], timeout=5)
            GLib.idle_add(self._status_row.set_subtitle, out.strip() if ok else "Not installed")

            ok, out, _err = _run_cmd(["docker", "compose", "version"], timeout=5)
            GLib.idle_add(self._compose_row.set_subtitle, out.strip() if ok else "Not available")
            GLib.idle_add(self._svc_row.refresh)

        _bg(_work)

    def _run_primary_docker_install(self, cmd: str) -> None:
        def _on_done(ok: bool) -> None:
            if not ok:
                return
            # Post-install: verify and enable service
            def _verify() -> None:
                systemd = SystemdManager()
                # Best effort enable/start
                ok_en = systemd.enable_unit("docker.service")
                ok_st = systemd.start_unit("docker.service")
                msg = "Installed; service enabled and started."
                if not ok_en or not ok_st:
                    msg = "Installed, but failed to enable or start docker.service. Check logs."
                GLib.idle_add(emit_utility_toast, msg, "info" if ok_en and ok_st else "error")
                GLib.idle_add(self._check_status)

            _bg(_verify)

        _run_shell_visible(cmd, self, on_finished=_on_done)


# ── Create container page ────────────────────────────────────


class _DockerCreatePage(Gtk.Box):
    """Form to create and run a new Docker container."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        # Image
        img_group = Adw.PreferencesGroup(
            title="Create Container",
            description="Fill in the fields and click Run to create a container.",
        )

        self._image_row = Adw.EntryRow(title="Image")
        self._image_row.set_text("nginx:latest")
        img_group.add(self._image_row)

        self._name_row = Adw.EntryRow(title="Container name (optional)")
        img_group.add(self._name_row)

        self.append(img_group)

        # Ports
        ports_group = Adw.PreferencesGroup(
            title="Port mappings",
            description="host:container — one per line (e.g. 8080:80)",
        )
        self._ports_entry = Gtk.TextView()
        self._ports_entry.set_monospace(True)
        self._ports_entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._ports_entry.get_buffer().set_text("8080:80")
        self._ports_entry.set_top_margin(8)
        self._ports_entry.set_bottom_margin(8)
        self._ports_entry.set_left_margin(10)
        self._ports_entry.set_right_margin(10)
        ports_scroll = Gtk.ScrolledWindow(
            hexpand=True, min_content_height=60, max_content_height=100,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        ports_scroll.set_child(self._ports_entry)
        ports_group.add(ports_scroll)
        self.append(ports_group)

        # Volumes
        vol_group = Adw.PreferencesGroup(
            title="Volume mounts",
            description="host_path:container_path — one per line",
        )
        self._vols_entry = Gtk.TextView()
        self._vols_entry.set_monospace(True)
        self._vols_entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._vols_entry.set_top_margin(8)
        self._vols_entry.set_bottom_margin(8)
        self._vols_entry.set_left_margin(10)
        self._vols_entry.set_right_margin(10)
        vols_scroll = Gtk.ScrolledWindow(
            hexpand=True, min_content_height=60, max_content_height=100,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        vols_scroll.set_child(self._vols_entry)
        vol_group.add(vols_scroll)
        self.append(vol_group)

        # Environment variables
        env_group = Adw.PreferencesGroup(
            title="Environment variables",
            description="KEY=VALUE — one per line",
        )
        self._env_entry = Gtk.TextView()
        self._env_entry.set_monospace(True)
        self._env_entry.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._env_entry.set_top_margin(8)
        self._env_entry.set_bottom_margin(8)
        self._env_entry.set_left_margin(10)
        self._env_entry.set_right_margin(10)
        env_scroll = Gtk.ScrolledWindow(
            hexpand=True, min_content_height=60, max_content_height=100,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        env_scroll.set_child(self._env_entry)
        env_group.add(env_scroll)
        self.append(env_group)

        # Options
        opts_group = Adw.PreferencesGroup(title="Options")

        self._detach_row = Adw.SwitchRow(title="Detached mode (-d)", subtitle="Run in background")
        self._detach_row.set_active(True)
        opts_group.add(self._detach_row)

        self._rm_row = Adw.SwitchRow(title="Auto-remove (--rm)", subtitle="Remove container when it stops")
        opts_group.add(self._rm_row)

        self._restart_row = Adw.ComboRow(title="Restart policy")
        self._restart_row.set_model(Gtk.StringList.new(["no", "always", "unless-stopped", "on-failure"]))
        self._restart_row.set_selected(0)
        opts_group.add(self._restart_row)

        self._extra_row = Adw.EntryRow(title="Extra flags (advanced)")
        self._extra_row.set_text("")
        opts_group.add(self._extra_row)

        self.append(opts_group)

        # Command preview + buttons
        preview_group = Adw.PreferencesGroup(title="Command preview")
        self._preview_label = Gtk.Label(xalign=0.0, wrap=True, selectable=True)
        self._preview_label.add_css_class("monospace")
        self._preview_label.set_margin_start(12)
        self._preview_label.set_margin_end(12)
        self._preview_label.set_margin_top(8)
        self._preview_label.set_margin_bottom(8)
        preview_group.add(self._preview_label)
        self.append(preview_group)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(6)

        preview_btn = Gtk.Button(label="Preview command")
        preview_btn.connect("clicked", lambda _b: self._update_preview())
        btn_box.append(preview_btn)

        copy_btn = Gtk.Button(label="Copy")
        copy_btn.connect("clicked", lambda _b: _copy(self._build_command()))
        btn_box.append(copy_btn)

        run_btn = Gtk.Button(label="Run")
        run_btn.add_css_class("suggested-action")
        run_btn.connect("clicked", lambda _b: self._run_container())
        btn_box.append(run_btn)

        self.append(btn_box)

        self._update_preview()

        # Examples
        ex_group = Adw.PreferencesGroup(
            title="Examples",
            description="Click any example to fill the form above.",
        )
        for ex_name, ex in [
            ("Nginx web server", {
                "image": "nginx:latest", "name": "my-nginx",
                "ports": "8080:80", "vols": "", "env": "",
                "detach": True, "rm": False, "restart": 0, "extra": "",
            }),
            ("PostgreSQL database", {
                "image": "postgres:16", "name": "my-postgres",
                "ports": "5432:5432", "vols": "pgdata:/var/lib/postgresql/data",
                "env": "POSTGRES_PASSWORD=mysecret\nPOSTGRES_USER=dev\nPOSTGRES_DB=appdb",
                "detach": True, "rm": False, "restart": 2, "extra": "",
            }),
            ("Redis cache", {
                "image": "redis:7-alpine", "name": "my-redis",
                "ports": "6379:6379", "vols": "", "env": "",
                "detach": True, "rm": False, "restart": 1, "extra": "",
            }),
            ("MySQL database", {
                "image": "mysql:8", "name": "my-mysql",
                "ports": "3306:3306", "vols": "mysqldata:/var/lib/mysql",
                "env": "MYSQL_ROOT_PASSWORD=rootpass\nMYSQL_DATABASE=appdb\nMYSQL_USER=dev\nMYSQL_PASSWORD=devpass",
                "detach": True, "rm": False, "restart": 2, "extra": "",
            }),
            ("MongoDB", {
                "image": "mongo:7", "name": "my-mongo",
                "ports": "27017:27017", "vols": "mongodata:/data/db",
                "env": "MONGO_INITDB_ROOT_USERNAME=admin\nMONGO_INITDB_ROOT_PASSWORD=secret",
                "detach": True, "rm": False, "restart": 2, "extra": "",
            }),
            ("Ubuntu shell (interactive)", {
                "image": "ubuntu:24.04", "name": "",
                "ports": "", "vols": "", "env": "",
                "detach": False, "rm": True, "restart": 0, "extra": "-it",
            }),
            ("Python dev container", {
                "image": "python:3.12-slim", "name": "py-dev",
                "ports": "8000:8000", "vols": ".:/app",
                "env": "PYTHONDONTWRITEBYTECODE=1",
                "detach": True, "rm": False, "restart": 0, "extra": "-w /app",
            }),
            ("Node.js app", {
                "image": "node:20-alpine", "name": "node-app",
                "ports": "3000:3000", "vols": ".:/app",
                "env": "NODE_ENV=development",
                "detach": True, "rm": False, "restart": 0, "extra": "-w /app",
            }),
        ]:
            row = Adw.ActionRow(title=ex_name, subtitle=ex["image"])
            row.set_activatable(True)
            row.connect("activated", lambda _r, e=ex: self._apply_example(e))
            use_btn = Gtk.Button(label="Use")
            use_btn.set_valign(Gtk.Align.CENTER)
            use_btn.add_css_class("suggested-action")
            use_btn.connect("clicked", lambda _b, e=ex: self._apply_example(e))
            row.add_suffix(use_btn)
            ex_group.add(row)
        self.append(ex_group)

    def _apply_example(self, ex: dict[str, Any]) -> None:
        self._image_row.set_text(ex["image"])
        self._name_row.set_text(ex.get("name", ""))
        self._ports_entry.get_buffer().set_text(ex.get("ports", ""))
        self._vols_entry.get_buffer().set_text(ex.get("vols", ""))
        self._env_entry.get_buffer().set_text(ex.get("env", ""))
        self._detach_row.set_active(ex.get("detach", True))
        self._rm_row.set_active(ex.get("rm", False))
        self._restart_row.set_selected(ex.get("restart", 0))
        self._extra_row.set_text(ex.get("extra", ""))
        self._update_preview()

    def _get_text(self, tv: Gtk.TextView) -> str:
        buf = tv.get_buffer()
        return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)

    def _build_command(self) -> str:
        parts = ["docker", "run"]

        if self._detach_row.get_active():
            parts.append("-d")
        if self._rm_row.get_active():
            parts.append("--rm")

        restart_idx = self._restart_row.get_selected()
        restart_vals = ["no", "always", "unless-stopped", "on-failure"]
        if restart_idx > 0:
            parts.extend(["--restart", restart_vals[restart_idx]])

        name = self._name_row.get_text().strip()
        if name:
            parts.extend(["--name", name])

        for line in self._get_text(self._ports_entry).splitlines():
            mapping = line.strip()
            if mapping:
                parts.extend(["-p", mapping])

        for line in self._get_text(self._vols_entry).splitlines():
            mount = line.strip()
            if mount:
                parts.extend(["-v", mount])

        for line in self._get_text(self._env_entry).splitlines():
            var = line.strip()
            if var and "=" in var:
                parts.extend(["-e", var])

        extra = self._extra_row.get_text().strip()
        if extra:
            parts.extend(extra.split())

        image = self._image_row.get_text().strip()
        if not image:
            image = "nginx:latest"
        parts.append(image)

        return " ".join(parts)

    def _update_preview(self) -> None:
        self._preview_label.set_text(self._build_command())

    def _run_container(self) -> None:
        image = self._image_row.get_text().strip()
        if not image:
            emit_utility_toast("Enter an image name.", "warning", timeout=4)
            return
        cmd = self._build_command()
        _run_shell(cmd)


# ── Log viewer dialog ────────────────────────────────────────


class _DockerLogDialog(Adw.Dialog):
    """Live-streaming docker logs in a scrollable text view."""

    def __init__(self, container_name: str, *, transient_for: Gtk.Window | None = None) -> None:
        super().__init__()
        self.set_title(f"Logs — {container_name}")
        self.set_content_width(780)
        self.set_content_height(520)

        self._container = container_name
        self._process: subprocess.Popen[str] | None = None
        self._follow = True

        # Header bar
        header = Adw.HeaderBar()

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        self._follow_btn = Gtk.ToggleButton(label="Follow")
        self._follow_btn.set_active(True)
        self._follow_btn.set_tooltip_text("Auto-scroll to new lines")
        self._follow_btn.connect("toggled", self._on_follow_toggled)
        toolbar.append(self._follow_btn)

        copy_btn = Gtk.Button(label="Copy all")
        copy_btn.set_tooltip_text("Copy full log to clipboard")
        copy_btn.connect("clicked", self._on_copy_all)
        toolbar.append(copy_btn)

        clear_btn = Gtk.Button(label="Clear")
        clear_btn.set_tooltip_text("Clear display")
        clear_btn.connect("clicked", self._on_clear)
        toolbar.append(clear_btn)

        header.pack_start(toolbar)

        # Text view
        self._textview = Gtk.TextView()
        self._textview.set_editable(False)
        self._textview.set_cursor_visible(False)
        self._textview.set_monospace(True)
        self._textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._textview.set_top_margin(8)
        self._textview.set_bottom_margin(8)
        self._textview.set_left_margin(10)
        self._textview.set_right_margin(10)
        self._buffer = self._textview.get_buffer()

        # Backend uses logback %highlight/%cyan in dev profile, which emits ANSI
        # escape sequences. The UI doesn't interpret them, so we strip ANSI and
        # re-apply colors via GTK text tags.
        self._tag_error = self._buffer.create_tag("docker_log_error", foreground="#ef4444")
        self._tag_warn = self._buffer.create_tag("docker_log_warn", foreground="#f59e0b")
        self._tag_info = self._buffer.create_tag("docker_log_info", foreground="#60a5fa")
        self._tag_debug = self._buffer.create_tag("docker_log_debug", foreground="#94a3b8")
        self._tag_trace = self._buffer.create_tag("docker_log_trace", foreground="#a78bfa")

        scroll = Gtk.ScrolledWindow(
            hexpand=True, vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_child(self._textview)
        self._scroll = scroll

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(header)
        content.append(scroll)
        self.set_child(content)

        self.connect("closed", self._on_closed)

        # Start streaming
        _bg(self._stream_logs)

    def _stream_logs(self) -> None:
        """Run `docker logs --follow --tail 200` and push lines to the UI."""
        try:
            self._process = subprocess.Popen(
                ["docker", "logs", "--follow", "--tail", "200", self._container],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except Exception as e:
            GLib.idle_add(self._append_text, f"Error: {e}\n")
            return

        for line in iter(self._process.stdout.readline, ""):
            if self._process is None:
                break
            GLib.idle_add(self._append_text, line)

        if self._process is not None:
            self._process.wait()
            GLib.idle_add(self._append_text, "\n--- stream ended ---\n")

    def _pick_level_tag(self, line: str) -> Any | None:
        m = _LOG_LEVEL_RE.search(line)
        if not m:
            return None
        level = m.group(1)
        return {
            "ERROR": self._tag_error,
            "WARN": self._tag_warn,
            "INFO": self._tag_info,
            "DEBUG": self._tag_debug,
            "TRACE": self._tag_trace,
        }.get(level)

    def _append_text(self, text: str) -> None:
        end_iter = self._buffer.get_end_iter()
        clean = _ANSI_ESCAPE_RE.sub("", text).replace("\r", "")
        tag = self._pick_level_tag(clean)
        if tag is not None:
            # Signature: insert_with_tags(iter, text, *tags)
            self._buffer.insert_with_tags(end_iter, clean, tag)
        else:
            self._buffer.insert(end_iter, clean)
        if self._follow:
            end_mark = self._buffer.create_mark(None, self._buffer.get_end_iter(), False)
            self._textview.scroll_mark_onscreen(end_mark)
            self._buffer.delete_mark(end_mark)

    def _on_follow_toggled(self, btn: Gtk.ToggleButton) -> None:
        self._follow = btn.get_active()
        if self._follow:
            end_mark = self._buffer.create_mark(None, self._buffer.get_end_iter(), False)
            self._textview.scroll_mark_onscreen(end_mark)
            self._buffer.delete_mark(end_mark)

    def _on_copy_all(self, _btn: Gtk.Button) -> None:
        text = self._buffer.get_text(
            self._buffer.get_start_iter(), self._buffer.get_end_iter(), False
        )
        _copy(text[:50000])

    def _on_clear(self, _btn: Gtk.Button) -> None:
        self._buffer.set_text("")

    def _on_closed(self, *_args: Any) -> None:
        proc = self._process
        self._process = None
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.kill()


# ── Containers page ─────────────────────────────────────────


class _DockerContainersPage(Gtk.Box):
    """List, start, stop, remove containers."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_bottom(6)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda _b: self._load_containers())
        toolbar.append(refresh_btn)

        self._show_all = Gtk.ToggleButton(label="Show stopped")
        self._show_all.set_tooltip_text("Include stopped containers")
        self._show_all.connect("toggled", lambda _b: self._load_containers())
        toolbar.append(self._show_all)

        self.append(toolbar)

        self._group = Adw.PreferencesGroup(
            title="Containers",
            description="Running and stopped containers on this host.",
        )
        self.append(self._group)

        self._empty_label = Gtk.Label(label="No containers found. Click Refresh.")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(20)
        self.append(self._empty_label)

        GLib.idle_add(self._load_containers)

    def _load_containers(self) -> None:
        def _work() -> None:
            cmd = ["docker", "ps", "--format", "{{json .}}"]
            if self._show_all.get_active():
                cmd.insert(2, "-a")
            ok, out, _err = _run_cmd(cmd, timeout=10)
            GLib.idle_add(self._populate, out if ok else "", ok)

        _bg(_work)

    def _populate(self, raw: str, success: bool) -> None:
        _clear_preferences_group_rows(self._group)

        if not success:
            self._empty_label.set_label("Docker not available or not running.")
            self._empty_label.set_visible(True)
            return

        containers: list[dict[str, str]] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        self._empty_label.set_visible(len(containers) == 0)
        if not containers:
            self._empty_label.set_label("No containers found.")
            return

        for c in containers:
            name = c.get("Names", "?")
            image = c.get("Image", "?")
            status = c.get("Status", "?")
            cid = c.get("ID", "")[:12]
            state = c.get("State", "").lower()

            row = Adw.ActionRow()
            row.set_title(name)
            row.set_subtitle(f"{image}  •  {status}  •  {cid}")

            if state == "running":
                stop_btn = Gtk.Button(icon_name="media-playback-stop-symbolic")
                stop_btn.set_valign(Gtk.Align.CENTER)
                stop_btn.set_tooltip_text("Stop container")
                stop_btn.connect("clicked", lambda _b, n=name: self._action("stop", n))
                row.add_suffix(stop_btn)
            else:
                start_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
                start_btn.set_valign(Gtk.Align.CENTER)
                start_btn.set_tooltip_text("Start container")
                start_btn.connect("clicked", lambda _b, n=name: self._action("start", n))
                row.add_suffix(start_btn)

            rm_btn = Gtk.Button(icon_name="user-trash-symbolic")
            rm_btn.set_valign(Gtk.Align.CENTER)
            rm_btn.set_tooltip_text("Remove container")
            rm_btn.add_css_class("destructive-action")
            rm_btn.connect("clicked", lambda _b, n=name: self._action("rm", n))
            row.add_suffix(rm_btn)

            logs_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
            logs_btn.set_valign(Gtk.Align.CENTER)
            logs_btn.set_tooltip_text("View logs")
            logs_btn.connect("clicked", lambda _b, n=name: self._show_logs(n))
            row.add_suffix(logs_btn)

            self._group.add(row)

    def _action(self, verb: str, name: str) -> None:
        def _work() -> None:
            ok, _out, err = _run_cmd(["docker", verb, name], timeout=30)
            msg = f"docker {verb} {name}: {'OK' if ok else err.strip()[:100]}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 5)
            GLib.idle_add(self._load_containers)

        _bg(_work)

    def _show_logs(self, name: str) -> None:
        win = self.get_root()
        dlg = _DockerLogDialog(name, transient_for=win if isinstance(win, Gtk.Window) else None)
        dlg.present()


# ── Images page ──────────────────────────────────────────────


class _DockerImagesPage(Gtk.Box):
    """List and remove Docker images."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_bottom(6)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda _b: self._load_images())
        toolbar.append(refresh_btn)

        pull_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._pull_entry = Gtk.Entry()
        self._pull_entry.set_placeholder_text("image:tag (e.g. nginx:latest)")
        self._pull_entry.set_hexpand(True)
        pull_btn = Gtk.Button(label="Pull")
        pull_btn.add_css_class("suggested-action")
        pull_btn.connect("clicked", lambda _b: self._pull_image())
        pull_box.append(self._pull_entry)
        pull_box.append(pull_btn)
        toolbar.append(pull_box)

        self.append(toolbar)

        self._group = Adw.PreferencesGroup(
            title="Images",
            description="Local Docker images.",
        )
        self.append(self._group)

        self._empty_label = Gtk.Label(label="No images found. Click Refresh.")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(20)
        self.append(self._empty_label)

        GLib.idle_add(self._load_images)

    def _pull_image(self) -> None:
        image = self._pull_entry.get_text().strip()
        if not image:
            emit_utility_toast("Enter an image name first.", "warning", timeout=4)
            return

        def _work() -> None:
            GLib.idle_add(emit_utility_toast, f"Pulling {image}…", "info", 3)
            ok, _out, err = _run_cmd(["docker", "pull", image], timeout=300)
            msg = f"Pull {image}: {'done' if ok else err.strip()[:120]}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 6)
            if ok:
                GLib.idle_add(self._load_images)

        _bg(_work)

    def _load_images(self) -> None:
        def _work() -> None:
            ok, out, _err = _run_cmd(["docker", "images", "--format", "{{json .}}"], timeout=10)
            GLib.idle_add(self._populate, out if ok else "", ok)

        _bg(_work)

    def _populate(self, raw: str, success: bool) -> None:
        _clear_preferences_group_rows(self._group)

        if not success:
            self._empty_label.set_label("Docker not available.")
            self._empty_label.set_visible(True)
            return

        images: list[dict[str, str]] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                images.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        self._empty_label.set_visible(len(images) == 0)
        if not images:
            self._empty_label.set_label("No images found.")
            return

        for img in images:
            repo = img.get("Repository", "<none>")
            tag = img.get("Tag", "latest")
            img_id = img.get("ID", "")[:12]
            size = img.get("Size", "?")

            row = Adw.ActionRow()
            row.set_title(f"{repo}:{tag}")
            row.set_subtitle(f"{img_id}  •  {size}")

            rm_btn = Gtk.Button(icon_name="user-trash-symbolic")
            rm_btn.set_valign(Gtk.Align.CENTER)
            rm_btn.set_tooltip_text("Remove image")
            rm_btn.add_css_class("destructive-action")
            rm_btn.connect("clicked", lambda _b, i=img_id: self._remove_image(i))
            row.add_suffix(rm_btn)
            self._group.add(row)

    def _remove_image(self, image_id: str) -> None:
        def _work() -> None:
            ok, _out, err = _run_cmd(["docker", "rmi", image_id], timeout=30)
            msg = f"Remove {image_id}: {'OK' if ok else err.strip()[:100]}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 5)
            GLib.idle_add(self._load_images)

        _bg(_work)


# ── Volumes page ─────────────────────────────────────────────


class _DockerVolumesPage(Gtk.Box):
    """List and manage Docker volumes."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_bottom(6)

        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda _b: self._load_volumes())
        toolbar.append(refresh_btn)

        create_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._vol_entry = Gtk.Entry()
        self._vol_entry.set_placeholder_text("volume name")
        self._vol_entry.set_hexpand(True)
        create_btn = Gtk.Button(label="Create")
        create_btn.add_css_class("suggested-action")
        create_btn.connect("clicked", lambda _b: self._create_volume())
        create_box.append(self._vol_entry)
        create_box.append(create_btn)
        toolbar.append(create_box)

        self.append(toolbar)

        self._group = Adw.PreferencesGroup(title="Volumes", description="Docker volumes on this host.")
        self.append(self._group)

        self._empty_label = Gtk.Label(label="No volumes found.")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(20)
        self.append(self._empty_label)

        GLib.idle_add(self._load_volumes)

    def _create_volume(self) -> None:
        name = self._vol_entry.get_text().strip()
        if not name:
            emit_utility_toast("Enter a volume name.", "warning", timeout=4)
            return

        def _work() -> None:
            ok, _out, err = _run_cmd(["docker", "volume", "create", name], timeout=10)
            msg = f"Volume '{name}': {'created' if ok else err.strip()[:100]}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 5)
            if ok:
                GLib.idle_add(self._load_volumes)
                GLib.idle_add(self._vol_entry.set_text, "")

        _bg(_work)

    def _load_volumes(self) -> None:
        def _work() -> None:
            ok, out, _err = _run_cmd(
                ["docker", "volume", "ls", "--format", "{{json .}}"], timeout=10
            )
            GLib.idle_add(self._populate, out if ok else "", ok)

        _bg(_work)

    def _populate(self, raw: str, success: bool) -> None:
        _clear_preferences_group_rows(self._group)

        if not success:
            self._empty_label.set_label("Docker not available.")
            self._empty_label.set_visible(True)
            return

        vols: list[dict[str, str]] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                vols.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        self._empty_label.set_visible(len(vols) == 0)
        for v in vols:
            name = v.get("Name", "?")
            driver = v.get("Driver", "local")
            row = Adw.ActionRow(title=name, subtitle=f"driver: {driver}")
            rm_btn = Gtk.Button(icon_name="user-trash-symbolic")
            rm_btn.set_valign(Gtk.Align.CENTER)
            rm_btn.set_tooltip_text("Remove volume")
            rm_btn.add_css_class("destructive-action")
            rm_btn.connect("clicked", lambda _b, n=name: self._remove_volume(n))
            row.add_suffix(rm_btn)
            self._group.add(row)

    def _remove_volume(self, name: str) -> None:
        def _work() -> None:
            ok, _out, err = _run_cmd(["docker", "volume", "rm", name], timeout=10)
            msg = f"Volume '{name}': {'removed' if ok else err.strip()[:100]}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 5)
            GLib.idle_add(self._load_volumes)

        _bg(_work)


# ── Networks page ────────────────────────────────────────────


class _DockerNetworksPage(Gtk.Box):
    """List Docker networks."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_bottom(6)
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.connect("clicked", lambda _b: self._load_networks())
        toolbar.append(refresh_btn)
        self.append(toolbar)

        self._group = Adw.PreferencesGroup(title="Networks", description="Docker networks on this host.")
        self.append(self._group)

        self._empty_label = Gtk.Label(label="No networks found.")
        self._empty_label.add_css_class("dim-label")
        self._empty_label.set_margin_top(20)
        self.append(self._empty_label)

        GLib.idle_add(self._load_networks)

    def _load_networks(self) -> None:
        def _work() -> None:
            ok, out, _err = _run_cmd(
                ["docker", "network", "ls", "--format", "{{json .}}"], timeout=10
            )
            GLib.idle_add(self._populate, out if ok else "", ok)

        _bg(_work)

    def _populate(self, raw: str, success: bool) -> None:
        _clear_preferences_group_rows(self._group)

        if not success:
            self._empty_label.set_label("Docker not available.")
            self._empty_label.set_visible(True)
            return

        nets: list[dict[str, str]] = []
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                nets.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        self._empty_label.set_visible(len(nets) == 0)
        for n in nets:
            name = n.get("Name", "?")
            driver = n.get("Driver", "?")
            scope = n.get("Scope", "?")
            row = Adw.ActionRow(title=name, subtitle=f"{driver}  •  {scope}")
            self._group.add(row)


# ── Cleanup page ─────────────────────────────────────────────


class _DockerCleanupPage(Gtk.Box):
    """Prune commands for containers, images, volumes, networks, system."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        group = Adw.PreferencesGroup(
            title="Cleanup",
            description="Service/package removal is handled in the Install tab. Prune containers, images, and system resources here.",
        )

        for label, cmd, desc in [
            ("Prune stopped containers", "docker container prune -f", "Remove all stopped containers"),
            ("Prune dangling images", "docker image prune -f", "Remove unused/dangling images"),
            ("Prune ALL unused images", "docker image prune -a -f", "Remove all images not used by containers"),
            ("Prune unused volumes", "docker volume prune -f", "Remove volumes not attached to containers"),
            ("Prune unused networks", "docker network prune -f", "Remove networks not used by containers"),
            ("Full system prune", "docker system prune -f", "Remove all stopped containers, dangling images, unused networks"),
            ("Full system prune (+ volumes)", "docker system prune --volumes -f", "Nuclear option — removes everything unused"),
        ]:
            row = Adw.ActionRow(title=label, subtitle=desc)

            copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.set_has_frame(False)
            copy_btn.add_css_class("flat")
            copy_btn.set_tooltip_text("Copy command")
            copy_btn.connect("clicked", lambda _b, c=cmd: _copy(c))
            row.add_suffix(copy_btn)

            run_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
            run_btn.set_valign(Gtk.Align.CENTER)
            run_btn.set_tooltip_text("Run now")
            run_btn.add_css_class("destructive-action")
            run_btn.connect("clicked", lambda _b, c=cmd, lbl=label: self._run_prune(c, lbl))
            row.add_suffix(run_btn)

            group.add(row)

        self.append(group)

        disk_group = Adw.PreferencesGroup(
            title="Disk Usage",
            description="Check how much space Docker is using.",
        )
        self._disk_row = Adw.ActionRow(title="docker system df", subtitle="Click Refresh to check")
        disk_refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        disk_refresh.set_valign(Gtk.Align.CENTER)
        disk_refresh.connect("clicked", lambda _b: self._check_disk())
        self._disk_row.add_suffix(disk_refresh)
        disk_group.add(self._disk_row)
        self.append(disk_group)

    def _run_prune(self, cmd: str, label: str) -> None:
        parts = cmd.split()

        def _work() -> None:
            GLib.idle_add(emit_utility_toast, f"Running: {label}…", "info", 3)
            ok, out, err = _run_cmd(parts, timeout=120)
            text = out.strip()[:200] if ok else err.strip()[:200]
            msg = f"{label}: {text or 'done'}"
            GLib.idle_add(emit_utility_toast, msg, "info" if ok else "error", 8)

        _bg(_work)

    def _check_disk(self) -> None:
        def _work() -> None:
            ok, out, _err = _run_cmd(["docker", "system", "df"], timeout=10)
            text = out.strip() if ok else "Docker not available"
            GLib.idle_add(self._disk_row.set_subtitle, text[:300])

        _bg(_work)


# ── Main panel ───────────────────────────────────────────────


class WorkstationDockerPanel(Gtk.Box):
    """Docker: subsection bar = Install | Containers | Images | Volumes | Networks | Cleanup."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kwargs)
        self._bar = WorkstationSubsectionBar(
            [
                ("install", "Install", _DockerInstallPage()),
                ("create", "Create", _DockerCreatePage()),
                ("containers", "Containers", _DockerContainersPage()),
                ("images", "Images", _DockerImagesPage()),
                ("volumes", "Volumes", _DockerVolumesPage()),
                ("networks", "Networks", _DockerNetworksPage()),
                ("cleanup", "Cleanup", _DockerCleanupPage()),
            ]
        )
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()
