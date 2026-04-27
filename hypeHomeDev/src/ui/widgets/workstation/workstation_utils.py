"""Shared workstation helpers: distro detection, subprocess checks, command rows."""

from __future__ import annotations

import json
from pathlib import Path
import logging
import re
import shlex
import shutil
import subprocess
import threading
import traceback
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.nav_helper import copy_plain_text_to_clipboard  # noqa: E402

_SHELL_PREAMBLE = """\
for f in ~/.bashrc ~/.zshrc /dev/null; do [ -f "$f" ] && . "$f" 2>/dev/null && break; done
[ -s "$HOME/.nvm/nvm.sh" ] && . "$HOME/.nvm/nvm.sh" 2>/dev/null
[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ] && . "$HOME/.sdkman/bin/sdkman-init.sh" 2>/dev/null
[ -d "$HOME/.pyenv/bin" ] && export PATH="$HOME/.pyenv/bin:$PATH" && eval "$(pyenv init -)" 2>/dev/null
[ -d "$HOME/.cargo/bin" ] && export PATH="$HOME/.cargo/bin:$PATH"
[ -d "$HOME/.local/bin" ] && export PATH="$HOME/.local/bin:$PATH"
[ -d "/usr/local/go/bin" ] && export PATH="/usr/local/go/bin:$PATH"
[ -d "$HOME/go/bin" ] && export PATH="$HOME/go/bin:$PATH"
"""


def detect_package_manager() -> str:
    """Return a short package-manager id from /etc/os-release (dnf, apt, pacman, …)."""
    os_release: dict[str, str] = {}
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    os_release[k] = v.strip('"')
    except OSError:
        return "unknown"
    distro = os_release.get("ID", "").lower()
    id_like = os_release.get("ID_LIKE", "").lower().split()
    all_ids = [distro, *id_like]
    mapping = [
        ("dnf", ["fedora", "rhel", "centos"]),
        ("apt", ["debian", "ubuntu", "linuxmint", "pop"]),
        ("pacman", ["arch", "manjaro", "endeavouros"]),
        ("zypper", ["opensuse", "suse"]),
        ("apk", ["alpine"]),
    ]
    for pm, families in mapping:
        if any(d in families for d in all_ids):
            return pm
    return "unknown"


PACKAGE_MANAGER = detect_package_manager()
_PKG_MANAGER = PACKAGE_MANAGER


def _run_cmd(cmd: list[str], *, timeout: float = 30) -> tuple[bool, str, str]:
    """Run a command synchronously, return (success, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, r.stdout, r.stderr
    except FileNotFoundError:
        return False, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def _run_check(cmd_str: str, *, timeout: float = 10) -> tuple[bool, str, str]:
    """Run a check command with dev-tool init scripts sourced."""
    full_cmd = _SHELL_PREAMBLE + cmd_str
    try:
        r = subprocess.run(
            ["bash", "-c", full_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return r.returncode == 0, r.stdout, r.stderr
    except FileNotFoundError:
        return False, "", "bash not found"
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)


def _bg(fn: Any) -> None:
    """Run *fn* in a background thread (fire-and-forget)."""
    threading.Thread(target=fn, daemon=True).start()


def _copy(text: str) -> None:
    if copy_plain_text_to_clipboard(text):
        emit_utility_toast("Copied.", "info", timeout=3)


def _distro_cmd(pkg: str = "", *, flatpak_id: str = "") -> str:
    """Install command for the detected package manager, or a Flatpak install line."""
    if flatpak_id:
        return f"flatpak install --user -y flathub {flatpak_id}"
    cmds = {
        "dnf": f"sudo dnf install -y {pkg}",
        "apt": f"sudo apt install -y {pkg}",
        "pacman": f"sudo pacman -S --noconfirm {pkg}",
        "zypper": f"sudo zypper install -y {pkg}",
        "apk": f"sudo apk add {pkg}",
    }
    return cmds.get(PACKAGE_MANAGER, f"# Install {pkg} with your package manager")


def _distro_remove(pkg: str) -> str:
    cmds = {
        "dnf": f"sudo dnf remove -y {pkg}",
        "apt": f"sudo apt remove -y {pkg}",
        "pacman": f"sudo pacman -Rns --noconfirm {pkg}",
        "zypper": f"sudo zypper remove -y {pkg}",
        "apk": f"sudo apk del {pkg}",
    }
    return cmds.get(PACKAGE_MANAGER, f"# Remove {pkg} with your package manager")


def _docker_run_shell_visible(
    cmd_str: str, widget: Gtk.Widget, *, on_finished: Any = None
) -> None:
    from ui.widgets.workstation.docker_manager import _run_shell_visible as _impl

    _impl(cmd_str, widget, on_finished=on_finished)


def _docker_open_in_terminal(cmd: str) -> None:
    from ui.widgets.workstation.docker_manager import _open_in_terminal as _impl

    _impl(cmd)


def _patch_config_file(path: str, tag: str, content: str) -> str:
    """
    Return a shell command that safely patches a config file.
    If the block with # HypeHome: [tag] exists, it replaces it.
    Otherwise, it appends it.
    """
    start_m = f"# HypeHome: [{tag}] START"
    end_m = f"# HypeHome: [{tag}] END"
    # Escaping for shell use
    safe_content = content.replace("'", "'\\''")

    # shell escape the markers for sed
    # Note: we use a simpler approach of 'delete then append' to ensure the order is consistent
    # and we don't end up with multiple blocks.
    cmd = (
        f"mkdir -p $(dirname '{path}') && touch '{path}' && "
        f"sed -i '/{re.escape(start_m)}/,/{re.escape(end_m)}/d' '{path}' && "
        f"printf '\\n{start_m}\\n{safe_content}\\n{end_m}\\n' >> '{path}' && "
        f"echo 'Updated {path} with [{tag}] block.'"
    )
    return cmd


def resolve_catalog_placeholders(text: str, catalog_json: dict[str, Any] | None = None) -> str:
    """Replace {{NAME}} tokens using a placeholders map (defaults to basic built-ins)."""
    # Base built-ins
    placeholders = {
        "GO_VERSION": "1.24.1",
        "GO_ARCH": "linux-amd64",
        "NVM_VERSION": "v0.40.1",
        "NODE_LTS": "--lts",
        "pkg_remove": _distro_remove("PACKAGENAME"),
    }

    # Merge with catalog if provided
    if catalog_json:
        cat_ph = catalog_json.get("placeholders")
        if isinstance(cat_ph, dict):
            placeholders.update(cat_ph)

    out = text
    # Sort keys by length descending to avoid partial matches (e.g. {{go}} vs {{go_ver}})
    for key, val in sorted(placeholders.items(), key=lambda x: len(x[0]), reverse=True):
        out = out.replace("{{" + key + "}}", str(val))
    return out


def safe_load_catalog(path: Path | str) -> dict[str, Any]:
    """Load JSON catalog data with robustness against I/O and parse errors."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError(f"Root object must be a dictionary: {p}")
        return data
    except (OSError, json.JSONDecodeError, ValueError) as e:
        log.error("Failed to load catalog %s: %s", p, e)
        log.debug(traceback.format_exc())
        # Return a 'safe' empty structure that won't crash the UI builders
        return {"id": "error", "error": str(e), "i18n": {"en": {"groups": []}}}


def sanitize_pango_markup(text: str) -> str:
    """Escape ampersands and other characters that break Pango markup parsing."""
    if not text:
        return ""
    return GLib.markup_escape_text(text)


def _find_list_box_descendant(widget: Gtk.Widget) -> Gtk.ListBox | None:
    """Return the first ``GtkListBox`` under *widget* (depth-first)."""
    if isinstance(widget, Gtk.ListBox):
        return widget
    child = widget.get_first_child()
    while child is not None:
        found = _find_list_box_descendant(child)
        if found is not None:
            return found
        child = child.get_next_sibling()
    return None


def _clear_preferences_group_rows(group: Adw.PreferencesGroup) -> None:
    """Remove user-added rows from *group* without touching Adwaita internals.

    ``AdwPreferencesGroup`` nests an internal ``GtkListBox``; rows are its children,
    not direct children of the group. Calling ``group.remove()`` on inner widgets
    triggers GTK CRITICALs (non-child / wrong parent).
    """
    lb = _find_list_box_descendant(group)
    if lb is None:
        return
    while True:
        row = lb.get_first_child()
        if row is None:
            break
        lb.remove(row)


def _add_row(
    group: Adw.PreferencesGroup,
    title: str,
    cmd: str,
    *,
    check_cmd: str | None = None,
    tag: str | None = None,
) -> None:
    """
    Add a row with Run + Copy buttons.
    If 'tag' is provided, the command is treated as a configuration patch.
    Format for tag: 'absolute_path:identifier'
    """
    display_cmd = cmd
    actual_cmd = cmd

    if tag and ":" in tag:
        # Configuration patch logic
        path, identifier = tag.split(":", 1)
        actual_cmd = _patch_config_file(path, identifier, cmd)
    else:
        actual_cmd = resolve_catalog_placeholders(cmd)

    safe_subtitle = GLib.markup_escape_text(display_cmd)
    row = Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=safe_subtitle)
    row.set_activatable(True)

    status_lbl: Gtk.Label | None = None
    recheck_fn = None

    if check_cmd:
        status_lbl = Gtk.Label(label="checking…")
        status_lbl.add_css_class("dim-label")
        status_lbl.add_css_class("caption")
        status_lbl.set_valign(Gtk.Align.CENTER)

        def _recheck(lbl: Gtk.Label = status_lbl, chk: str = check_cmd) -> None:
            lbl.set_label("checking…")
            def _work() -> None:
                # Resolve placeholders for check too
                real_check = resolve_catalog_placeholders(chk)
                ok, _out, _err = _run_check(real_check)
                text = "installed" if ok else "not found"
                GLib.idle_add(lbl.set_label, text)
            _bg(_work)

        recheck_fn = _recheck

    def _on_finished(_success: bool, fn: object = recheck_fn) -> None:
        if callable(fn):
            GLib.idle_add(fn)

    cb = _on_finished if recheck_fn else None
    row.connect(
        "activated",
        lambda _r, c=actual_cmd, f=cb: _docker_run_shell_visible(c, _r, on_finished=f),
    )

    run_btn = Gtk.Button(icon_name="media-playback-start-symbolic")
    run_btn.set_valign(Gtk.Align.CENTER)
    run_btn.set_tooltip_text("Run this command")
    run_btn.add_css_class("suggested-action")
    run_btn.connect(
        "clicked",
        lambda _b, c=actual_cmd, f=cb: _docker_run_shell_visible(c, _b, on_finished=f),
    )
    row.add_suffix(run_btn)

    copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
    copy_btn.set_valign(Gtk.Align.CENTER)
    copy_btn.set_has_frame(False)
    copy_btn.add_css_class("flat")
    copy_btn.set_tooltip_text("Copy command")
    copy_btn.connect("clicked", lambda _b, c=display_cmd: _copy(c))
    row.add_suffix(copy_btn)

    if status_lbl is not None:
        row.add_suffix(status_lbl)
        GLib.idle_add(recheck_fn)

    group.add(row)


def _add_tty_row(
    group: Adw.PreferencesGroup,
    title: str,
    cmd: str,
) -> None:
    """Add a row that opens *cmd* in a real terminal window (for TUI/interactive commands)."""
    actual_cmd = resolve_catalog_placeholders(cmd)
    safe_subtitle = GLib.markup_escape_text(cmd)
    row = Adw.ActionRow(title=GLib.markup_escape_text(title), subtitle=safe_subtitle)
    row.set_activatable(True)
    row.connect("activated", lambda _r, c=actual_cmd: _docker_open_in_terminal(c))

    run_btn = Gtk.Button(icon_name="utilities-terminal-symbolic")
    run_btn.set_valign(Gtk.Align.CENTER)
    run_btn.set_tooltip_text("Open in terminal")
    run_btn.add_css_class("suggested-action")
    run_btn.connect("clicked", lambda _b, c=actual_cmd: _docker_open_in_terminal(c))
    row.add_suffix(run_btn)

    copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
    copy_btn.set_valign(Gtk.Align.CENTER)
    copy_btn.set_has_frame(False)
    copy_btn.add_css_class("flat")
    copy_btn.set_tooltip_text("Copy command")
    copy_btn.connect("clicked", lambda _b, c=cmd: _copy(c))
    row.add_suffix(copy_btn)

    group.add(row)


def _add_runnable_row(
    group: Adw.PreferencesGroup,
    title: str,
    cmd: str,
    *,
    check_cmd: str | None = None,
    tag: str | None = None,
) -> None:
    """Consolidated alias for :func:`_add_row`."""
    _add_row(group, title, cmd, check_cmd=check_cmd, tag=tag)


def _add_terminal_row(
    group: Adw.PreferencesGroup,
    title: str,
    cmd: str,
) -> None:
    """Consolidated alias for :func:`_add_tty_row`."""
    _add_tty_row(group, title, cmd)


def _open_in_terminal(cmd: str) -> None:
    _docker_open_in_terminal(cmd)


def _run_shell_visible(
    cmd_str: str, widget: Gtk.Widget, *, on_finished: Any = None
) -> None:
    _docker_run_shell_visible(cmd_str, widget, on_finished=on_finished)


class WorkstationCatalogPage(Gtk.Box):
    """
    Base class for a data-driven catalog page.
    Agent B will use this to generate rows from JSON.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kwargs)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

    def add_catalog_group(self, title: str, description: str) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(
            title=GLib.markup_escape_text(title),
            description=GLib.markup_escape_text(description),
        )
        self.append(group)
        return group
