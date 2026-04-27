"""Workstation → Services: Tailscale, Dropbox, NordVPN, Bitwarden, 1Password.

The Services hub still lists Docker (and other catalog entries) from ``services.json``;
full Docker tooling lives under Workstation → Servers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
import time
from pathlib import Path
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.models import AppInfo  # noqa: E402
from core.setup.package_installer import PackageInstaller  # noqa: E402
from core.setup.systemd_manager import SystemdManager  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.subsection_bar import WorkstationSubsectionBar  # noqa: E402
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    PACKAGE_MANAGER as _PKG_MANAGER,
)
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    _add_row,
    _add_tty_row,
    _bg,
    _distro_remove,
    _run_cmd,
)

log = logging.getLogger(__name__)

# Process-service catalog fields are later run without a login shell where possible;
# reject obvious shell injection / chaining markers at load time.
_PROCESS_CMD_FORBIDDEN = frozenset(
    {";", "|", "&", "`", "\n", "\r", "$", "(", ")", "<", ">", "\x00"},
)
_PROCESS_CMD_FORBIDDEN_SUBSTR = ("&&", "||", "$(", "${", ";;", ">&")


def _binary_catalog_token_ok(s: str) -> bool:
    """True if *s* is a single program name or path fragment (no spaces / shell)."""
    return bool(s) and bool(re.fullmatch(r"[A-Za-z0-9_.\-/]+", s))


def _process_cmd_catalog_ok(s: str) -> bool:
    if not isinstance(s, str):
        return False
    t = s.strip()
    if not t or any(c in t for c in _PROCESS_CMD_FORBIDDEN) or any(x in t for x in _PROCESS_CMD_FORBIDDEN_SUBSTR):
        return False
    try:
        shlex.split(t, posix=True)
    except ValueError:
        return False
    return len(t) <= 2048


def _sanitize_process_service_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Drop unsafe ``kind: process`` shell fragments from a catalog entry (mutates a copy)."""
    if str(entry.get("kind") or "") != "process":
        return entry
    out = dict(entry)
    sid = str(out.get("id", "") or "?")
    for key in ("start_cmd", "stop_cmd", "status_cmd"):
        raw = out.get(key)
        if raw is None or raw == "":
            out[key] = ""
            continue
        if not isinstance(raw, str):
            log.warning("services.json: service %r: %s must be a string, ignoring", sid, key)
            out[key] = ""
            continue
        if not _process_cmd_catalog_ok(raw):
            log.warning("services.json: service %r: rejected unsafe or invalid %s", sid, key)
            out[key] = ""
        else:
            out[key] = raw.strip()
    b = out.get("binary")
    if b is None or b == "":
        out["binary"] = ""
    elif not isinstance(b, str):
        log.warning("services.json: service %r: binary must be a string, ignoring", sid)
        out["binary"] = ""
    elif not _binary_catalog_token_ok(b.strip()):
        log.warning("services.json: service %r: rejected unsafe or invalid binary", sid)
        out["binary"] = ""
    else:
        out["binary"] = b.strip()
    return out


def _argv_from_process_cmd(cmd: str) -> list[str] | None:
    """Parse a process start/stop/status line into argv (no shell). Returns None if unsafe or invalid."""
    t = cmd.strip()
    if not t:
        return None
    if any(c in t for c in _PROCESS_CMD_FORBIDDEN) or any(x in t for x in _PROCESS_CMD_FORBIDDEN_SUBSTR):
        return None
    try:
        parts = shlex.split(t, posix=True)
    except ValueError:
        return None
    return parts or None


def _argv_binary_installed_probe(binary: str) -> list[str] | None:
    """Argv for ``command -v <binary>`` via login shell (binary is shlex-quoted)."""
    b = binary.strip()
    if not _binary_catalog_token_ok(b):
        return None
    return ["sh", "-lc", f"command -v {shlex.quote(b)} >/dev/null 2>&1"]


# ═══════════════════════════════════════════════════════════════
#  TAILSCALE
# ═══════════════════════════════════════════════════════════════


class _TailscaleHubPage(Gtk.Box):
    """Phase 3: Use generic ServiceFactoryRow for install + daemon controls."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)
        self._systemd = SystemdManager()

        svc = Adw.PreferencesGroup(
            title="Service Control",
            description=(
                "Install + start/stop is managed by the generic systemd row "
                "using D-Bus + PolKit (no shell sudo wrappers)."
            ),
        )
        service = next((s for s in _load_service_catalog() if str(s.get("id", "")) == "tailscale"), None)
        if service is not None:
            svc.add(
                ServiceFactoryRow(
                    service,
                    systemd=self._systemd,
                    installer=self._installer,
                    executor=self._executor,
                ),
            )
        else:
            svc.add(
                Adw.ActionRow(
                    title="Tailscale",
                    subtitle="Service definition missing from services.json",
                ),
            )
        self.append(svc)

        refs = Adw.PreferencesGroup(
            title="References",
            description="Official docs and quick links.",
        )
        _add_row(refs, "Open Tailscale docs", "xdg-open https://tailscale.com/kb")
        _add_row(refs, "Open Tailscale admin", "xdg-open https://login.tailscale.com/admin/machines")
        self.append(refs)


class _TailscaleConnectPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        auth = Adw.PreferencesGroup(
            title="Authenticate",
            description="Log in to your Tailscale account.",
        )
        _add_tty_row(auth, "Log in (browser)", "sudo tailscale up")
        _add_tty_row(auth, "Log in (auth key)", "sudo tailscale up --authkey=YOUR_KEY")
        _add_tty_row(auth, "Log out", "sudo tailscale logout")
        self.append(auth)

        net = Adw.PreferencesGroup(
            title="Network",
            description="View and manage your tailnet.",
        )
        _add_row(net, "Network status", "tailscale status")
        _add_row(net, "Show my IPs", "tailscale ip")
        _add_row(net, "Ping a device", "tailscale ping DEVICE_NAME")
        _add_row(net, "DNS status", "tailscale dns status")
        _add_row(net, "Netcheck", "tailscale netcheck")
        self.append(net)


class _TailscaleFeaturesPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        exit_node = Adw.PreferencesGroup(
            title="Exit Node",
            description="Route traffic through another Tailscale device.",
        )
        _add_row(exit_node, "Advertise as exit node", "sudo tailscale up --advertise-exit-node")
        _add_row(exit_node, "Use an exit node", "sudo tailscale up --exit-node=DEVICE_NAME")
        _add_row(exit_node, "Stop using exit node", "sudo tailscale up --exit-node=")
        self.append(exit_node)

        subnet = Adw.PreferencesGroup(
            title="Subnet Router",
            description="Expose local network subnets to your tailnet.",
        )
        _add_row(subnet, "Advertise subnet", "sudo tailscale up --advertise-routes=192.168.1.0/24")
        _add_row(subnet, "Accept routes", "sudo tailscale up --accept-routes")
        self.append(subnet)

        ssh = Adw.PreferencesGroup(
            title="Tailscale SSH",
            description="SSH into devices using Tailscale identity — no keys needed.",
        )
        _add_row(ssh, "Enable SSH server", "sudo tailscale up --ssh")
        _add_tty_row(ssh, "SSH to device", "ssh user@DEVICE_NAME")
        self.append(ssh)

        share = Adw.PreferencesGroup(
            title="Taildrop (File Sharing)",
            description="Send files between devices on your tailnet.",
        )
        _add_row(share, "Send file", "tailscale file cp FILE DEVICE_NAME:")
        _add_row(share, "Receive files", "tailscale file get .")
        self.append(share)

        funnel = Adw.PreferencesGroup(
            title="Funnel &amp; Serve",
            description="Expose local services to the internet via Tailscale.",
        )
        _add_row(funnel, "Serve local port", "tailscale serve http / http://localhost:3000")
        _add_row(funnel, "Funnel to internet", "tailscale funnel 443")
        _add_row(funnel, "Stop serving", "tailscale serve off")
        self.append(funnel)


class _TailscaleUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Service/package removal is handled in the Service tab. Keep deep cleanup here.",
        )
        _add_row(rm, "Remove state", "sudo rm -rf /var/lib/tailscale")
        self.append(rm)


class WorkstationTailscalePanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("service-hub", "Service", _TailscaleHubPage()),
            ("connect", "Connect", _TailscaleConnectPage()),
            ("features", "Features", _TailscaleFeaturesPage()),
            ("uninstall", "Uninstall", _TailscaleUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  DROPBOX
# ═══════════════════════════════════════════════════════════════


class _DropboxSyncPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status = Adw.PreferencesGroup(
            title="Sync Status",
            description="Check current sync progress and file states.",
        )
        _add_row(status, "Sync status", "dropbox status")
        _add_row(status, "File status", "dropbox filestatus ~/Dropbox/FILE")
        _add_row(status, "Folder list", "ls ~/Dropbox")
        self.append(status)

        selective = Adw.PreferencesGroup(
            title="Selective Sync",
            description="Exclude specific folders from syncing to save disk space.",
        )
        _add_row(selective, "List excluded folders", "dropbox exclude list")
        _add_row(selective, "Exclude a folder", "dropbox exclude add ~/Dropbox/FOLDER")
        _add_row(selective, "Include a folder", "dropbox exclude remove ~/Dropbox/FOLDER")
        self.append(selective)

        throttle = Adw.PreferencesGroup(
            title="Bandwidth",
            description="Control upload and download speed limits.",
        )
        _add_row(throttle, "Set upload limit (KB/s)", "dropbox throttle upload 100")
        _add_row(throttle, "Set download limit (KB/s)", "dropbox throttle download 200")
        _add_row(throttle, "Unlimited", "dropbox throttle unlimited")
        self.append(throttle)


class _DropboxSharingPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        sharing = Adw.PreferencesGroup(
            title="Share Links",
            description="Generate public links to files and folders in your Dropbox.",
        )
        _add_row(sharing, "Create share link", "dropbox sharelink ~/Dropbox/FILE")
        self.append(sharing)

        lan = Adw.PreferencesGroup(
            title="LAN Sync",
            description="Sync faster between machines on the same local network.",
        )
        _add_row(lan, "Enable LAN sync", "dropbox lansync y")
        _add_row(lan, "Disable LAN sync", "dropbox lansync n")
        self.append(lan)


class _DropboxHubPage(Gtk.Box):
    """Dropbox process-managed hub page (install/start/stop/remove)."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)

        svc = Adw.PreferencesGroup(
            title="Service Control",
            description="Dropbox is managed as a user process (not systemd).",
        )
        service = next((s for s in _load_service_catalog() if str(s.get("id", "")) == "dropbox"), None)
        if service is not None:
            svc.add(
                ProcessServiceFactoryRow(
                    service,
                    installer=self._installer,
                    executor=self._executor,
                ),
            )
        else:
            svc.add(
                Adw.ActionRow(
                    title="Dropbox",
                    subtitle="Service definition missing from services.json",
                ),
            )
        self.append(svc)

        refs = Adw.PreferencesGroup(
            title="References",
            description="Official docs and account links.",
        )
        _add_row(refs, "Open Dropbox help", "xdg-open https://help.dropbox.com/")
        _add_row(refs, "Open Dropbox account", "xdg-open https://www.dropbox.com/account")
        self.append(refs)


class _DropboxCleanupPage(Gtk.Box):
    """Cleanup page for local Dropbox data/config artifacts."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Cleanup",
            description="Service/package removal is handled in the Service tab. Keep local cleanup here.",
        )
        _add_row(rm, "Remove daemon files", "rm -rf ~/.dropbox-dist")
        _add_row(rm, "Remove config", "rm -rf ~/.dropbox")
        _add_row(rm, "Remove synced data", "rm -rf ~/Dropbox")
        self.append(rm)


class WorkstationDropboxPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("service-hub", "Service", _DropboxHubPage()),
            ("sync", "Sync", _DropboxSyncPage()),
            ("sharing", "Sharing", _DropboxSharingPage()),
            ("cleanup", "Cleanup", _DropboxCleanupPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  NORDVPN
# ═══════════════════════════════════════════════════════════════


class _NordVPNHubPage(Gtk.Box):
    """Phase 4: Generic install + daemon controls through ServiceFactoryRow."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)
        self._systemd = SystemdManager()

        svc = Adw.PreferencesGroup(
            title="Service Control",
            description="Install + start/stop via D-Bus + PolKit.",
        )
        service = next((s for s in _load_service_catalog() if str(s.get("id", "")) == "nordvpn"), None)
        if service is not None:
            svc.add(
                ServiceFactoryRow(
                    service,
                    systemd=self._systemd,
                    installer=self._installer,
                    executor=self._executor,
                ),
            )
        else:
            svc.add(
                Adw.ActionRow(
                    title="NordVPN",
                    subtitle="Service definition missing from services.json",
                ),
            )
        self.append(svc)

        refs = Adw.PreferencesGroup(
            title="References",
            description="Official docs and account portal.",
        )
        _add_row(refs, "Open NordVPN docs", "xdg-open https://support.nordvpn.com/")
        _add_row(refs, "Open Nord Account", "xdg-open https://my.nordaccount.com/")
        self.append(refs)


class _NordVPNAccountPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        auth = Adw.PreferencesGroup(
            title="Account",
            description="Authenticate with your NordVPN credentials.",
        )
        _add_tty_row(auth, "Login", "nordvpn login")
        _add_tty_row(auth, "Login (token)", "nordvpn login --token YOUR_TOKEN")
        _add_row(auth, "Logout", "nordvpn logout")
        _add_row(auth, "Account info", "nordvpn account")
        self.append(auth)


class _NordVPNConnectPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        quick = Adw.PreferencesGroup(
            title="Quick Connect",
            description="Connect to the fastest available server.",
        )
        _add_row(quick, "Quick connect", "nordvpn connect")
        _add_row(quick, "Disconnect", "nordvpn disconnect")
        _add_row(quick, "Status", "nordvpn status")
        self.append(quick)

        location = Adw.PreferencesGroup(
            title="By Location",
            description="Connect to a specific country or city.",
        )
        _add_row(location, "Connect to country", "nordvpn connect United_States")
        _add_row(location, "Connect to city", "nordvpn connect Germany Berlin")
        _add_row(location, "List countries", "nordvpn countries")
        _add_row(location, "List cities", "nordvpn cities United_States")
        self.append(location)

        special = Adw.PreferencesGroup(
            title="Specialty Servers",
            description="P2P, Double VPN, Onion, and dedicated IP servers.",
        )
        _add_row(special, "P2P servers", "nordvpn connect --group P2P")
        _add_row(special, "Double VPN", "nordvpn connect --group Double_VPN")
        _add_row(special, "Onion over VPN", "nordvpn connect --group Onion_Over_VPN")
        _add_row(special, "Dedicated IP", "nordvpn connect --group Dedicated_IP")
        _add_row(special, "List server groups", "nordvpn groups")
        self.append(special)


class _NordVPNSettingsPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        safety = Adw.PreferencesGroup(
            title="Kill Switch &amp; Firewall",
            description="Prevent traffic leaks if the VPN drops.",
        )
        _add_row(safety, "Enable Kill Switch", "nordvpn set killswitch on")
        _add_row(safety, "Disable Kill Switch", "nordvpn set killswitch off")
        _add_row(safety, "Enable firewall", "nordvpn set firewall on")
        _add_row(safety, "Disable firewall", "nordvpn set firewall off")
        self.append(safety)

        auto = Adw.PreferencesGroup(
            title="Auto-connect",
            description="Automatically connect on startup.",
        )
        _add_row(auto, "Enable auto-connect", "nordvpn set autoconnect on")
        _add_row(auto, "Auto-connect to country", "nordvpn set autoconnect on United_States")
        _add_row(auto, "Disable auto-connect", "nordvpn set autoconnect off")
        self.append(auto)

        proto = Adw.PreferencesGroup(
            title="Protocol &amp; Technology",
            description="Switch between NordLynx (WireGuard) and OpenVPN.",
        )
        _add_row(proto, "Use NordLynx (faster)", "nordvpn set technology NordLynx")
        _add_row(proto, "Use OpenVPN", "nordvpn set technology OpenVPN")
        _add_row(proto, "Set UDP protocol", "nordvpn set protocol UDP")
        _add_row(proto, "Set TCP protocol", "nordvpn set protocol TCP")
        self.append(proto)

        dns = Adw.PreferencesGroup(
            title="DNS &amp; Threat Protection",
            description="Custom DNS and ad/malware blocking.",
        )
        _add_row(dns, "Threat Protection Lite on", "nordvpn set threatprotectionlite on")
        _add_row(dns, "Threat Protection Lite off", "nordvpn set threatprotectionlite off")
        _add_row(dns, "Custom DNS", "nordvpn set dns 1.1.1.1 8.8.8.8")
        _add_row(dns, "Reset DNS", "nordvpn set dns off")
        self.append(dns)

        mesh = Adw.PreferencesGroup(
            title="Meshnet",
            description="Private encrypted network between your devices.",
        )
        _add_row(mesh, "Enable Meshnet", "nordvpn set meshnet on")
        _add_row(mesh, "Disable Meshnet", "nordvpn set meshnet off")
        _add_row(mesh, "List peers", "nordvpn meshnet peer list")
        self.append(mesh)

        show = Adw.PreferencesGroup(
            title="Current Settings",
            description="View all active NordVPN settings.",
        )
        _add_row(show, "Show settings", "nordvpn settings")
        self.append(show)


class _NordVPNUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Service/package removal is handled in the Service tab. Keep session cleanup here.",
        )
        _add_row(rm, "Disconnect", "nordvpn disconnect")
        _add_row(rm, "Logout", "nordvpn logout")
        self.append(rm)


class WorkstationNordVPNPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("service-hub", "Service", _NordVPNHubPage()),
            ("account", "Account", _NordVPNAccountPage()),
            ("connect", "Connect", _NordVPNConnectPage()),
            ("settings", "Settings", _NordVPNSettingsPage()),
            ("uninstall", "Uninstall", _NordVPNUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  BITWARDEN
# ═══════════════════════════════════════════════════════════════


class _BitwardenInstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status_grp = Adw.PreferencesGroup(
            title="Status",
            description="Check Bitwarden installation.",
        )
        self._desk_row = Adw.ActionRow(title="Desktop app", subtitle="Checking…")
        self._cli_row = Adw.ActionRow(title="CLI (bw)", subtitle="Checking…")
        self._is_alive = True
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _b: self._refresh())
        self._desk_row.add_suffix(refresh)
        status_grp.add(self._desk_row)
        status_grp.add(self._cli_row)
        self.append(status_grp)

        desktop = Adw.PreferencesGroup(
            title="Desktop App",
            description="Install the Bitwarden desktop password manager.",
        )
        _add_row(desktop, "Install (Flatpak)", "flatpak install --user -y flathub com.bitwarden.desktop",
                 check_cmd="flatpak info com.bitwarden.desktop")
        _add_row(desktop, "Install (Snap)", "sudo snap install bitwarden")
        self.append(desktop)

        cli = Adw.PreferencesGroup(
            title="CLI",
            description="Command-line interface for scripting and automation.",
        )
        _add_row(cli, "Install CLI (Snap)", "sudo snap install bw", check_cmd="bw --version")
        _add_row(cli, "Install CLI (npm)", "npm install -g @bitwarden/cli")
        self.append(cli)

        GLib.idle_add(self._refresh)

    def do_unrealize(self) -> None:
        self._is_alive = False
        Gtk.Box.do_unrealize(self)

    def _refresh(self) -> None:
        if not self._is_alive:
            return
        def _work() -> None:
            ok1, _o, _e = _run_cmd(["flatpak", "info", "com.bitwarden.desktop"], timeout=5)
            if not self._is_alive:
                return
            GLib.idle_add(self._apply_bitwarden_status, ok1, "installed", 1)
            ok2, out, _e2 = _run_cmd(["bw", "--version"], timeout=5)
            if not self._is_alive:
                return
            GLib.idle_add(self._apply_bitwarden_status, ok2, out.strip(), 2)

        _bg(_work)

    def _apply_bitwarden_status(self, ok: bool, label: str, target: int) -> bool:
        if not self._is_alive:
            return False
        if target == 1:
            self._desk_row.set_subtitle(label if ok else "not found")
        else:
            self._cli_row.set_subtitle(label if ok else "not found")
        return False


class _BitwardenAccountPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        auth = Adw.PreferencesGroup(
            title="Authentication",
            description="Log in and manage your vault session.",
        )
        _add_tty_row(auth, "Login", "bw login")
        _add_tty_row(auth, "Login (API key)", "bw login --apikey")
        _add_tty_row(auth, "Unlock vault", "bw unlock")
        _add_row(auth, "Lock vault", "bw lock")
        _add_row(auth, "Logout", "bw logout")
        _add_row(auth, "Check status", "bw status")
        self.append(auth)

        config = Adw.PreferencesGroup(
            title="Server Config",
            description="Point CLI at a self-hosted Bitwarden server.",
        )
        _add_row(config, "Set server URL", "bw config server https://your-server.com")
        _add_row(config, "Reset to cloud", "bw config server https://vault.bitwarden.com")
        self.append(config)


class _BitwardenVaultPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        sync = Adw.PreferencesGroup(
            title="Sync",
            description="Synchronize your local vault cache with the server.",
        )
        _add_row(sync, "Sync vault", "bw sync")
        _add_row(sync, "Last sync time", "bw sync --last")
        self.append(sync)

        browse = Adw.PreferencesGroup(
            title="Browse Items",
            description="List and search items in your vault.",
        )
        _add_row(browse, "List all items", "bw list items")
        _add_row(browse, "Search items", "bw list items --search QUERY")
        _add_row(browse, "List folders", "bw list folders")
        _add_row(browse, "List collections", "bw list collections")
        _add_row(browse, "List organizations", "bw list organizations")
        self.append(browse)

        access = Adw.PreferencesGroup(
            title="Access Items",
            description="Get specific passwords, notes, and attachments.",
        )
        _add_row(access, "Get item", "bw get item ITEM_NAME")
        _add_row(access, "Get password", "bw get password ITEM_NAME")
        _add_row(access, "Get username", "bw get username ITEM_NAME")
        _add_row(access, "Get TOTP code", "bw get totp ITEM_NAME")
        _add_row(access, "Get notes", "bw get notes ITEM_NAME")
        self.append(access)

        create = Adw.PreferencesGroup(
            title="Create &amp; Edit",
            description="Add new items or modify existing ones.",
        )
        _add_row(create, "Create item (from JSON)", 'echo \'{"type":1,"name":"Example","login":{"username":"user","password":"pass"}}\' | bw create item')
        _add_row(create, "Create folder", 'echo \'{"name":"MyFolder"}\' | bw create folder')
        _add_row(create, "Edit item", "bw edit item ITEM_ID ENCODED_JSON")
        _add_row(create, "Delete item", "bw delete item ITEM_ID")
        self.append(create)

        gen = Adw.PreferencesGroup(
            title="Password Generator",
            description="Generate secure passwords and passphrases.",
        )
        _add_row(gen, "Generate password (20 chars)", "bw generate -ulns --length 20")
        _add_row(gen, "Generate passphrase", "bw generate --passphrase --words 5 --separator -")
        _add_row(gen, "Generate (letters only)", "bw generate -ul --length 16")
        self.append(gen)


class _BitwardenExportPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        export = Adw.PreferencesGroup(
            title="Export",
            description="Export your vault. WARNING: exported files are unencrypted unless you choose encrypted format.",
        )
        _add_row(export, "Export as JSON", "bw export --format json")
        _add_row(export, "Export as CSV", "bw export --format csv")
        _add_row(export, "Export encrypted", "bw export --format encrypted_json")
        self.append(export)

        imp = Adw.PreferencesGroup(
            title="Import",
            description="Import passwords from another manager or backup.",
        )
        _add_row(imp, "Import (Bitwarden JSON)", "bw import bitwardenjson FILEPATH")
        _add_row(imp, "Import (LastPass CSV)", "bw import lastpasscsv FILEPATH")
        _add_row(imp, "Import (1Password)", "bw import 1password1pux FILEPATH")
        _add_row(imp, "Import (Chrome CSV)", "bw import chromecsv FILEPATH")
        self.append(imp)


class _BitwardenUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Remove Bitwarden desktop app and CLI.",
        )
        _add_row(rm, "Uninstall desktop (Flatpak)", "flatpak uninstall --user com.bitwarden.desktop")
        _add_row(rm, "Uninstall desktop (Snap)", "sudo snap remove bitwarden")
        _add_row(rm, "Uninstall CLI (Snap)", "sudo snap remove bw")
        _add_row(rm, "Uninstall CLI (npm)", "npm uninstall -g @bitwarden/cli")
        _add_row(rm, "Remove config", "rm -rf ~/.config/Bitwarden")
        self.append(rm)


class WorkstationBitwardenPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("install", "Install", _BitwardenInstallPage()),
            ("account", "Account", _BitwardenAccountPage()),
            ("vault", "Vault", _BitwardenVaultPage()),
            ("export", "Import / Export", _BitwardenExportPage()),
            ("uninstall", "Uninstall", _BitwardenUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  1PASSWORD
# ═══════════════════════════════════════════════════════════════


class _OnePasswordInstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        status_grp = Adw.PreferencesGroup(
            title="Status",
            description="Check 1Password installation.",
        )
        self._desk_row = Adw.ActionRow(title="Desktop app", subtitle="Checking…")
        self._cli_row = Adw.ActionRow(title="CLI (op)", subtitle="Checking…")
        refresh = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh.set_valign(Gtk.Align.CENTER)
        refresh.connect("clicked", lambda _b: self._refresh())
        self._desk_row.add_suffix(refresh)
        status_grp.add(self._desk_row)
        status_grp.add(self._cli_row)
        self.append(status_grp)

        desktop = Adw.PreferencesGroup(
            title="Desktop App",
            description="1Password desktop with browser integration and SSH agent.",
        )
        _add_row(desktop, "Install (Flatpak)", "flatpak install --user -y flathub com.onepassword.OnePassword",
                 check_cmd="flatpak info com.onepassword.OnePassword")
        self.append(desktop)

        cli = Adw.PreferencesGroup(
            title="CLI (op)",
            description="Powerful CLI for scripting, secrets injection, and SSH key management.",
        )
        cli_cmds: dict[str, str] = {
            "dnf": (
                "sudo rpm --import https://downloads.1password.com/linux/keys/1password.asc"
                " && printf '[1password-cli]\\nname=1Password CLI\\n"
                "baseurl=https://downloads.1password.com/linux/rpm/stable/$basearch\\n"
                "enabled=1\\ngpgcheck=1\\ngpgkey=https://downloads.1password.com/linux/keys/1password.asc\\n'"
                " | sudo tee /etc/yum.repos.d/1password-cli.repo > /dev/null"
                " && sudo dnf install -y 1password-cli"
            ),
            "apt": (
                "curl -sS https://downloads.1password.com/linux/keys/1password.asc"
                " | sudo gpg --dearmor --output /usr/share/keyrings/1password-archive-keyring.gpg"
                " && echo 'deb [arch=amd64 signed-by=/usr/share/keyrings/1password-archive-keyring.gpg]"
                " https://downloads.1password.com/linux/debian/amd64 stable main'"
                " | sudo tee /etc/apt/sources.list.d/1password.list"
                " && sudo apt update && sudo apt install -y 1password-cli"
            ),
            "pacman": "sudo pacman -S --noconfirm 1password-cli",
        }
        op_cmd = cli_cmds.get(_PKG_MANAGER, "# See https://developer.1password.com/docs/cli/get-started")
        _add_row(cli, "Install 1Password CLI", op_cmd, check_cmd="op --version")
        self.append(cli)

        GLib.idle_add(self._refresh)

    def _refresh(self) -> None:
        def _work() -> None:
            ok1, _o, _e = _run_cmd(["flatpak", "info", "com.onepassword.OnePassword"], timeout=5)
            GLib.idle_add(self._desk_row.set_subtitle, "installed" if ok1 else "not found")
            ok2, out, _e2 = _run_cmd(["op", "--version"], timeout=5)
            GLib.idle_add(self._cli_row.set_subtitle, out.strip() if ok2 else "not found")
        _bg(_work)


class _OnePasswordAccountPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        auth = Adw.PreferencesGroup(
            title="Authentication",
            description="Sign in and manage sessions.",
        )
        _add_tty_row(auth, "Sign in", "op signin")
        _add_tty_row(auth, "Add account (first time)", "op account add")
        _add_row(auth, "Who am I", "op whoami")
        _add_row(auth, "List accounts", "op account list")
        _add_row(auth, "Forget account", "op account forget ACCOUNT_SHORTHAND")
        self.append(auth)

        biometric = Adw.PreferencesGroup(
            title="Biometric Unlock",
            description="Use system auth to unlock — requires desktop app.",
        )
        _add_tty_row(biometric, "Enable biometric", "op signin --account SHORTHAND")
        self.append(biometric)


class _OnePasswordVaultPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        vaults = Adw.PreferencesGroup(
            title="Vaults",
            description="Manage your 1Password vaults.",
        )
        _add_row(vaults, "List vaults", "op vault list")
        _add_row(vaults, "Get vault details", "op vault get VAULT_NAME")
        _add_row(vaults, "Create vault", "op vault create NEW_VAULT_NAME")
        _add_row(vaults, "Delete vault", "op vault delete VAULT_NAME")
        self.append(vaults)

        items = Adw.PreferencesGroup(
            title="Items",
            description="Browse and retrieve items from your vaults.",
        )
        _add_row(items, "List items", "op item list")
        _add_row(items, "List items in vault", "op item list --vault VAULT_NAME")
        _add_row(items, "Get item", "op item get ITEM_NAME")
        _add_row(items, "Get password field", "op item get ITEM_NAME --fields password")
        _add_row(items, "Get OTP", "op item get ITEM_NAME --otp")
        self.append(items)

        create = Adw.PreferencesGroup(
            title="Create &amp; Edit",
            description="Add and modify items.",
        )
        _add_row(create, "Create login item",
                 "op item create --category Login --title TITLE --vault VAULT "
                 "username=USER password=PASS")
        _add_row(create, "Create with generated password",
                 "op item create --category Login --title TITLE "
                 "--generate-password=20,letters,digits,symbols")
        _add_row(create, "Create secure note",
                 'op item create --category "Secure Note" --title TITLE notesPlain=CONTENT')
        _add_row(create, "Edit item", "op item edit ITEM_NAME field=VALUE")
        _add_row(create, "Delete item", "op item delete ITEM_NAME")
        _add_row(create, "Move to trash", "op item delete ITEM_NAME --archive")
        self.append(create)

        gen = Adw.PreferencesGroup(
            title="Password Generator",
            description="Generate strong passwords via the CLI.",
        )
        _add_row(gen, "Generate password (20 chars)",
                 "op item create --category Password --generate-password=20,letters,digits,symbols --title temp")
        self.append(gen)


class _OnePasswordSSHPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        agent = Adw.PreferencesGroup(
            title="SSH Agent",
            description="Use 1Password as your SSH key manager. Keys are stored in your vault.",
        )
        _add_row(agent, "List SSH keys", "op item list --categories 'SSH Key'")
        _add_row(agent, "Test SSH agent", "ssh-add -l")
        self.append(agent)

        setup = Adw.PreferencesGroup(
            title="Setup",
            description="Configure your shell to use the 1Password SSH agent.",
        )
        _add_row(setup, "Add to SSH config",
                 "Host *\n  IdentityAgent ~/.1password/agent.sock\n",
                 tag="~/.ssh/config:1password")
        _add_row(setup, "Set SSH_AUTH_SOCK",
                 'echo "export SSH_AUTH_SOCK=~/.1password/agent.sock" >> ~/.bashrc')
        self.append(setup)

        secrets = Adw.PreferencesGroup(
            title="Secrets Automation",
            description="Inject secrets into env vars, config files, and CI/CD.",
        )
        _add_row(secrets, "Read a secret reference",
                 "op read op://VAULT/ITEM/FIELD")
        _add_row(secrets, "Inject secrets into command",
                 "op run -- your-command")
        _add_row(secrets, "Inject secrets into .env",
                 "op inject -i .env.tpl -o .env")
        self.append(secrets)


class _OnePasswordUninstallPage(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12, **kw)
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(14)
        self.set_margin_bottom(18)

        rm = Adw.PreferencesGroup(
            title="Uninstall",
            description="Remove 1Password desktop and CLI.",
        )
        _add_row(rm, "Uninstall desktop (Flatpak)", "flatpak uninstall --user com.onepassword.OnePassword")
        _add_row(rm, "Uninstall CLI", _distro_remove("1password-cli"))
        _add_row(rm, "Remove config", "rm -rf ~/.config/1Password ~/.config/op")
        self.append(rm)


class WorkstationOnePasswordPanel(Gtk.Box):
    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._bar = WorkstationSubsectionBar([
            ("install", "Install", _OnePasswordInstallPage()),
            ("account", "Account", _OnePasswordAccountPage()),
            ("vault", "Vault", _OnePasswordVaultPage()),
            ("ssh", "SSH & Secrets", _OnePasswordSSHPage()),
            ("uninstall", "Uninstall", _OnePasswordUninstallPage()),
        ])
        self.append(self._bar)

    def reset_subsections(self) -> None:
        self._bar.reset_to_first()


# ═══════════════════════════════════════════════════════════════
#  GENERIC SERVICES HUB (PHASE 2 FACTORY ROWS)
# ═══════════════════════════════════════════════════════════════


def _load_service_catalog() -> list[dict[str, Any]]:
    path = Path(__file__).with_name("data") / "services.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw.get("services") or []
        out: list[dict[str, Any]] = []
        for e in entries:
            if not isinstance(e, dict):
                continue
            out.append(_sanitize_process_service_entry(e))
        return out
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        log.exception("Failed to load services catalog: %s", path)
        return []


class ServiceFactoryRow(Adw.ActionRow):
    """Generic row for a systemd-backed service entry."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        systemd: SystemdManager,
        installer: PackageInstaller,
        executor: HostExecutor,
    ) -> None:
        name = str(service.get("name", "Service"))
        desc = str((service.get("description") or {}).get("en", "") or "")
        super().__init__(title=name, subtitle=desc)
        self._service = service
        self._systemd = systemd
        self._installer = installer
        self._executor = executor
        self._busy = False
        self._updating_switch = False
        self._refresh_seq = 0
        self._watchdog_source_id: int = 0
        self._is_alive = True

        self._state_led = Gtk.Label(label="●")
        self._state_led.add_css_class("dim-label")
        self._state_led.set_valign(Gtk.Align.CENTER)
        self.add_prefix(self._state_led)

        self._state_lbl = Gtk.Label(label="checking…")
        self._state_lbl.add_css_class("caption")
        self._state_lbl.add_css_class("dim-label")
        self._state_lbl.set_valign(Gtk.Align.CENTER)
        self.add_suffix(self._state_lbl)

        self._toggle = Gtk.Switch()
        self._toggle.set_valign(Gtk.Align.CENTER)
        self._toggle.set_tooltip_text("Start/Stop service")
        self._toggle.connect("notify::active", self._on_toggle)
        self.add_suffix(self._toggle)

        self._install_btn = Gtk.Button(label="Install")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.set_valign(Gtk.Align.CENTER)
        self._install_btn.connect("clicked", self._on_install_clicked)
        self.add_suffix(self._install_btn)

        self._remove_btn = Gtk.Button(label="Remove")
        self._remove_btn.add_css_class("destructive-action")
        self._remove_btn.set_valign(Gtk.Align.CENTER)
        self._remove_btn.connect("clicked", self._on_remove_clicked)
        self.add_suffix(self._remove_btn)

        self._refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        self._refresh_btn.set_has_frame(False)
        self._refresh_btn.add_css_class("flat")
        self._refresh_btn.set_valign(Gtk.Align.CENTER)
        self._refresh_btn.connect("clicked", lambda _b: self.refresh())
        self.add_suffix(self._refresh_btn)

        self.refresh()

    def do_unrealize(self) -> None:
        self._is_alive = False
        if self._watchdog_source_id:
            GLib.source_remove(self._watchdog_source_id)
            self._watchdog_source_id = 0
        Adw.ActionRow.do_unrealize(self)

    def refresh(self) -> None:
        if self._busy:
            return
        if self._watchdog_source_id:
            GLib.source_remove(self._watchdog_source_id)
            self._watchdog_source_id = 0
        self._refresh_seq += 1
        seq = self._refresh_seq
        self._state_lbl.set_label("checking…")

        unit = str(self._service.get("unit", "") or "")
        binary = str(self._service.get("binary", "") or "")

        def _work() -> None:
            installed = False
            timed_out = False
            if binary:
                probe = _argv_binary_installed_probe(binary)
                if probe is None:
                    installed = False
                else:
                    res = self._executor.run_sync(probe, timeout=5)
                    installed = res.success
                    timed_out = "timed out" in (res.stderr or "").lower()
            state = self._systemd.get_unit_state(unit) if unit else None
            GLib.idle_add(self._apply_state, installed, state, timed_out, seq)

        _bg(_work)

        def _watchdog() -> bool:
            self._watchdog_source_id = 0
            if seq != self._refresh_seq:
                return False
            if self._state_lbl.get_label().strip().lower().startswith("checking"):
                self._state_led.set_markup('<span foreground="#f59e0b">●</span>')
                self._state_lbl.set_label("Status probe timed out")
                self._toggle.set_sensitive(False)
                self._install_btn.set_visible(True)
                self._remove_btn.set_visible(False)
            return False

        self._watchdog_source_id = GLib.timeout_add_seconds(8, _watchdog)

    def _apply_state(
        self,
        installed: bool,
        state: Any,
        timed_out: bool = False,
        seq: int | None = None,
    ) -> bool:
        if not self._is_alive:
            return False
        if seq is not None and seq != self._refresh_seq:
            return False
        active = str(getattr(state, "active_state", "") or "")
        sub = str(getattr(state, "sub_state", "") or "")
        load = str(getattr(state, "load_state", "") or "")

        if not installed:
            self._state_led.set_markup('<span foreground="#94a3b8">●</span>')
            self._state_lbl.set_label("Status check timed out" if timed_out else "Not installed")
            self._install_btn.set_visible(True)
            self._remove_btn.set_visible(False)
            self._toggle.set_sensitive(False)
            return False

        self._install_btn.set_visible(False)
        self._remove_btn.set_visible(True)
        unit_known = bool(state is not None and load and load != "not-found")
        self._toggle.set_sensitive(unit_known)
        running = active == "active"
        self._updating_switch = True
        self._toggle.set_active(running)
        self._updating_switch = False

        if active == "active":
            self._state_led.set_markup('<span foreground="#22c55e">●</span>')
            self._state_lbl.set_label(f"Running ({sub or 'active'})")
        elif active == "failed":
            self._state_led.set_markup('<span foreground="#ef4444">●</span>')
            self._state_lbl.set_label("Failed")
        elif unit_known:
            self._state_led.set_markup('<span foreground="#9ca3af">●</span>')
            self._state_lbl.set_label(f"Stopped ({active or 'inactive'})")
        else:
            self._state_led.set_markup('<span foreground="#9ca3af">●</span>')
            self._state_lbl.set_label("Installed, unit missing")
        return False

    def _on_toggle(self, sw: Gtk.Switch, _pspec: Any) -> None:
        if self._updating_switch or self._busy:
            return
        unit = str(self._service.get("unit", "") or "")
        if not unit:
            # UI ARTIFACT FIX: Finding 17 - Surface missing configuration
            emit_utility_toast(f"No systemd unit defined for {self.get_title()}", "warning")
            self._updating_switch = True
            sw.set_active(not sw.get_active())
            self._updating_switch = False
            return
        target_on = sw.get_active()
        self._busy = True
        self._toggle.set_sensitive(False)

        def _work() -> None:
            ok = self._systemd.start_unit(unit) if target_on else self._systemd.stop_unit(unit)
            # D-Bus StartUnit/StopUnit return when the job is queued; wait until state matches.
            if ok:
                for _ in range(50):
                    st = self._systemd.get_unit_state(unit)
                    active = st is not None and st.active_state == "active"
                    if active == target_on:
                        break
                    time.sleep(0.1)
                else:
                    st2 = self._systemd.get_unit_state(unit)
                    active2 = st2 is not None and st2.active_state == "active"
                    ok = active2 == target_on
            GLib.idle_add(self._after_action, ok, "Service updated." if ok else "Service action failed.")

        _bg(_work)

    def _on_install_clicked(self, _btn: Gtk.Button) -> None:
        if self._busy:
            return
        pkg = str(self._service.get("package_name", "") or "")
        name = str(self._service.get("name", pkg) or pkg)
        unit = str(self._service.get("unit", "") or "")
        if not pkg:
            emit_utility_toast("No package configured for this service.", "error")
            return
        self._busy = True
        self._install_btn.set_sensitive(False)

        def _work() -> None:
            async def _install() -> bool:
                await self._installer.initialize()
                app = AppInfo(
                    id=f"service:{pkg}",
                    name=name,
                    description=f"Service package for {name}",
                    icon="application-x-executable-symbolic",
                    package_name=pkg,
                    category="service",
                    ui_category="service",
                )
                ok = await self._installer.install_app(app)
                return ok

            try:
                ok = asyncio.run(_install())
            except Exception:
                log.exception("Service install failed for %s", pkg)
                ok = False
            if ok and unit:
                # Post-install: report enable/start separately (avoid success toasts when unit is dead).
                ok_en = self._systemd.enable_unit(unit)
                ok_st = self._systemd.start_unit(unit)
                if ok_en and ok_st:
                    final_toast = "Installed; service enabled and started."
                elif ok_en:
                    final_toast = "Installed and enabled, but failed to start the service."
                elif ok_st:
                    final_toast = "Installed and started, but failed to enable the service."
                else:
                    final_toast = "Installed, but failed to enable or start the service."
                if not ok_en or not ok_st:
                    log.warning("Post-install activation failed for %s (enable=%s, start=%s)", unit, ok_en, ok_st)
            else:
                final_toast = "Installed." if ok else "Install failed."

            GLib.idle_add(self._after_action, ok, final_toast)

        _bg(_work)

    def _on_remove_clicked(self, _btn: Gtk.Button) -> None:
        if self._busy:
            return
        pkg = str(self._service.get("package_name", "") or "")
        name = str(self._service.get("name", pkg) or pkg)
        unit = str(self._service.get("unit", "") or "")
        flatpak_id = str(self._service.get("flatpak_id", "") or "")
        if not pkg and not flatpak_id:
            emit_utility_toast("No package configured for this service.", "error")
            return
        self._busy = True
        self._remove_btn.set_sensitive(False)
        self._toggle.set_sensitive(False)

        def _work() -> None:
            # Normalize lifecycle first (best effort), then uninstall package.
            if unit:
                self._systemd.stop_unit(unit)
                self._systemd.disable_unit(unit)

            async def _remove() -> bool:
                await self._installer.initialize()
                app = AppInfo(
                    id=f"service:{pkg or flatpak_id}",
                    name=name,
                    description=f"Service package for {name}",
                    icon="application-x-executable-symbolic",
                    package_name=pkg or flatpak_id,
                    flatpak_id=flatpak_id or None,
                    category="flatpak" if flatpak_id else (_PKG_MANAGER or "service"),
                    ui_category="service",
                )
                return await self._installer.remove_installed_app(app)

            try:
                ok = asyncio.run(_remove())
            except Exception:
                log.exception("Service remove failed for %s", name)
                ok = False
            GLib.idle_add(self._after_action, ok, "Removed." if ok else "Remove failed.")

        _bg(_work)

    def _after_action(self, ok: bool, toast: str) -> bool:
        self._busy = False
        self._install_btn.set_sensitive(True)
        self._remove_btn.set_sensitive(True)
        self._toggle.set_sensitive(True)
        emit_utility_toast(toast, "info" if ok else "error")
        self.refresh()
        return False


class ProcessServiceFactoryRow(Adw.ActionRow):
    """Generic row for process-managed services (non-systemd daemons)."""

    def __init__(
        self,
        service: dict[str, Any],
        *,
        installer: PackageInstaller,
        executor: HostExecutor,
    ) -> None:
        name = str(service.get("name", "Service"))
        desc = str((service.get("description") or {}).get("en", "") or "")
        super().__init__(title=name, subtitle=desc)
        self._service = service
        self._installer = installer
        self._executor = executor
        self._busy = False
        self._updating_switch = False
        self._refresh_seq = 0
        self._watchdog_source_id: int = 0
        self._is_alive = True

        self._state_led = Gtk.Label(label="●")
        self._state_led.add_css_class("dim-label")
        self._state_led.set_valign(Gtk.Align.CENTER)
        self.add_prefix(self._state_led)

        self._state_lbl = Gtk.Label(label="checking…")
        self._state_lbl.add_css_class("caption")
        self._state_lbl.add_css_class("dim-label")
        self._state_lbl.set_valign(Gtk.Align.CENTER)
        self.add_suffix(self._state_lbl)

        self._toggle = Gtk.Switch()
        self._toggle.set_valign(Gtk.Align.CENTER)
        self._toggle.set_tooltip_text("Start/Stop process")
        self._toggle.connect("notify::active", self._on_toggle)
        self.add_suffix(self._toggle)

        self._install_btn = Gtk.Button(label="Install")
        self._install_btn.add_css_class("suggested-action")
        self._install_btn.set_valign(Gtk.Align.CENTER)
        self._install_btn.connect("clicked", self._on_install_clicked)
        self.add_suffix(self._install_btn)

        self._remove_btn = Gtk.Button(label="Remove")
        self._remove_btn.add_css_class("destructive-action")
        self._remove_btn.set_valign(Gtk.Align.CENTER)
        self._remove_btn.connect("clicked", self._on_remove_clicked)
        self.add_suffix(self._remove_btn)

        self.refresh()

    def do_unrealize(self) -> None:
        if self._watchdog_source_id:
            GLib.source_remove(self._watchdog_source_id)
            self._watchdog_source_id = 0
        Adw.ActionRow.do_unrealize(self)

    def refresh(self) -> None:
        if self._busy:
            return
        if self._watchdog_source_id:
            GLib.source_remove(self._watchdog_source_id)
            self._watchdog_source_id = 0
        self._refresh_seq += 1
        seq = self._refresh_seq
        self._state_lbl.set_label("checking…")
        binary = str(self._service.get("binary", "") or "")
        status_cmd = str(self._service.get("status_cmd", "") or "")

        def _work() -> None:
            installed = False
            timed_out = False
            if binary:
                probe = _argv_binary_installed_probe(binary)
                if probe is None:
                    installed = False
                else:
                    res = self._executor.run_sync(probe, timeout=5)
                    installed = res.success
                    timed_out = "timed out" in (res.stderr or "").lower()
            running = False
            if installed and status_cmd:
                st_argv = _argv_from_process_cmd(status_cmd)
                if st_argv is None:
                    running = False
                else:
                    res2 = self._executor.run_sync(st_argv, timeout=5)
                    out = (res2.stdout or "").strip().lower()
                    running = res2.success and ("running" in out or out in {"true", "yes", "up"})
            GLib.idle_add(self._apply_state, installed, running, timed_out, seq)

        _bg(_work)

        def _watchdog() -> bool:
            self._watchdog_source_id = 0
            if seq != self._refresh_seq:
                return False
            if self._state_lbl.get_label().strip().lower().startswith("checking"):
                self._state_led.set_markup('<span foreground="#f59e0b">●</span>')
                self._state_lbl.set_label("Status probe timed out")
                self._toggle.set_sensitive(False)
                self._install_btn.set_visible(True)
                self._remove_btn.set_visible(False)
            return False

        self._watchdog_source_id = GLib.timeout_add_seconds(8, _watchdog)

    def _apply_state(
        self,
        installed: bool,
        running: bool,
        timed_out: bool = False,
        seq: int | None = None,
    ) -> bool:
        if not self._is_alive:
            return False
        if seq is not None and seq != self._refresh_seq:
            return False
        if not installed:
            self._state_led.set_markup('<span foreground="#94a3b8">●</span>')
            self._state_lbl.set_label("Status check timed out" if timed_out else "Not installed")
            self._install_btn.set_visible(True)
            self._remove_btn.set_visible(False)
            self._toggle.set_sensitive(False)
            return False

        self._install_btn.set_visible(False)
        self._remove_btn.set_visible(True)
        self._toggle.set_sensitive(True)
        self._updating_switch = True
        self._toggle.set_active(running)
        self._updating_switch = False
        if running:
            self._state_led.set_markup('<span foreground="#22c55e">●</span>')
            self._state_lbl.set_label("Running")
        else:
            self._state_led.set_markup('<span foreground="#9ca3af">●</span>')
            self._state_lbl.set_label("Stopped")
        return False

    def _on_toggle(self, sw: Gtk.Switch, _pspec: Any) -> None:
        if self._updating_switch or self._busy:
            return
        cmd = str(self._service.get("start_cmd", "") or "") if sw.get_active() else str(self._service.get("stop_cmd", "") or "")
        if not cmd:
            emit_utility_toast("No start/stop command configured for this service.", "warning")
            self._updating_switch = True
            sw.set_active(not sw.get_active())
            self._updating_switch = False
            return
        self._busy = True
        self._toggle.set_sensitive(False)

        def _work() -> None:
            argv = _argv_from_process_cmd(cmd)
            if argv is None:
                GLib.idle_add(
                    self._after_action,
                    False,
                    "Invalid or disallowed process command (check services.json).",
                )
                return
            res = self._executor.run_sync(argv)
            GLib.idle_add(self._after_action, res.success, "Process updated." if res.success else "Process action failed.")

        _bg(_work)

    def _on_install_clicked(self, _btn: Gtk.Button) -> None:
        if self._busy:
            return
        pkg = str(self._service.get("package_name", "") or "")
        flatpak_id = str(self._service.get("flatpak_id", "") or "")
        name = str(self._service.get("name", pkg) or pkg)
        if not pkg and not flatpak_id:
            emit_utility_toast("No package configured for this service.", "error")
            return
        self._busy = True
        self._install_btn.set_sensitive(False)

        def _work() -> None:
            async def _install() -> bool:
                await self._installer.initialize()
                app = AppInfo(
                    id=f"service:{pkg or flatpak_id}",
                    name=name,
                    description=f"Service package for {name}",
                    icon="application-x-executable-symbolic",
                    package_name=pkg or flatpak_id,
                    flatpak_id=flatpak_id or None,
                    category="service",
                    ui_category="service",
                )
                return await self._installer.install_app(app)

            try:
                ok = asyncio.run(_install())
            except Exception:
                log.exception("Process-service install failed for %s", name)
                ok = False
            GLib.idle_add(self._after_action, ok, "Installed." if ok else "Install failed.")

        _bg(_work)

    def _on_remove_clicked(self, _btn: Gtk.Button) -> None:
        if self._busy:
            return
        pkg = str(self._service.get("package_name", "") or "")
        flatpak_id = str(self._service.get("flatpak_id", "") or "")
        name = str(self._service.get("name", pkg) or pkg)
        self._busy = True
        self._remove_btn.set_sensitive(False)

        def _work() -> None:
            async def _remove() -> bool:
                await self._installer.initialize()
                has_flatpak = False
                if flatpak_id:
                    r = self._executor.run_sync(["flatpak", "info", flatpak_id])
                    has_flatpak = r.success
                app = AppInfo(
                    id=f"service:{pkg or flatpak_id}",
                    name=name,
                    description=f"Service package for {name}",
                    icon="application-x-executable-symbolic",
                    package_name=pkg or flatpak_id,
                    flatpak_id=flatpak_id or None,
                    category="flatpak" if has_flatpak else (_PKG_MANAGER or "service"),
                    ui_category="service",
                )
                return await self._installer.remove_installed_app(app)

            try:
                ok = asyncio.run(_remove())
            except Exception:
                log.exception("Process-service remove failed for %s", name)
                ok = False
            GLib.idle_add(self._after_action, ok, "Removed." if ok else "Remove failed.")

        _bg(_work)

    def _after_action(self, ok: bool, toast: str) -> bool:
        self._busy = False
        self._install_btn.set_sensitive(True)
        self._remove_btn.set_sensitive(True)
        self._toggle.set_sensitive(True)
        emit_utility_toast(toast, "info" if ok else "error")
        self.refresh()
        return False


class WorkstationServicesHubPanel(Gtk.Box):
    """Data-driven Services hub using `services.json` + SystemdManager."""

    def __init__(self, **kw: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)
        self._systemd = SystemdManager()
        self._rows: list[Any] = []

        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(
            title="Service Hub",
            description="Live service state via systemd D-Bus. Start/Stop without shell wrappers.",
        )
        for service in _load_service_catalog():
            sid = str(service.get("id", "") or "")
            if sid not in {"tailscale", "docker", "nordvpn", "dropbox", "ollama"}:
                continue
            kind = str(service.get("kind", "systemd") or "systemd")
            if kind == "process":
                row = ProcessServiceFactoryRow(
                    service,
                    installer=self._installer,
                    executor=self._executor,
                )
            else:
                row = ServiceFactoryRow(
                    service,
                    systemd=self._systemd,
                    installer=self._installer,
                    executor=self._executor,
                )
            self._rows.append(row)
            group.add(row)
        page.add(group)
        self.append(page)

        self._refresh_timer_id = GLib.timeout_add_seconds(5, self._refresh_loop)

    def do_unrealize(self) -> None:
        """Cleanup timer when widget is hidden/destroyed (Negative Feedback Fix)."""
        if self._refresh_timer_id:
            GLib.source_remove(self._refresh_timer_id)
            self._refresh_timer_id = 0
        Gtk.Box.do_unrealize(self)

    def _refresh_loop(self) -> bool:
        for row in self._rows:
            row.refresh()
        return True

    def reset_subsections(self) -> None:
        # Keep existing API shape used by parent panel.
        for row in self._rows:
            row.refresh()


# ═══════════════════════════════════════════════════════════════
#  COMBINED SERVICES PANEL
# ═══════════════════════════════════════════════════════════════

_SERVICE_TABS: list[tuple[str, str, type]] = [
    ("hub", "Guide", WorkstationServicesHubPanel),
    ("tailscale", "Tailscale", WorkstationTailscalePanel),
    ("dropbox", "Dropbox", WorkstationDropboxPanel),
    ("nordvpn", "NordVPN", WorkstationNordVPNPanel),
    ("bitwarden", "Bitwarden", WorkstationBitwardenPanel),
    ("1password", "1Password", WorkstationOnePasswordPanel),
]


class WorkstationServicesPanel(Gtk.Box):
    """Top-level Services panel: Hub | Tailscale | Dropbox | NordVPN | Bitwarden | 1Password.

    Each tab shows a full sub-panel with its own subsection bar, so we do NOT
    wrap children in ScrolledWindow (the inner bars handle their own scrolling).
    """

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
        for sid, title, cls in _SERVICE_TABS:
            child = cls()
            self._children.append(child)
            self._stack.add_titled(child, sid, title)

        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        self.append(switcher)
        self.append(sep)
        self.append(self._stack)

    def reset_subsections(self) -> None:
        self._stack.set_visible_child_name("hub")
        for child in self._children:
            reset = getattr(child, "reset_subsections", None)
            if callable(reset):
                reset()
