"""Linux-hosts style monitor overview for Workstation → Servers (single local host + containers)."""

from __future__ import annotations

import json
import logging
import re
import socket
import time
from dataclasses import dataclass, field
from typing import Any

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import GLib, Gtk, Pango  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from ui.widgets.workstation.workstation_utils import _bg  # noqa: E402

log = logging.getLogger(__name__)

_POLL_SECONDS = 4
CHART_Y = 10.0  # normalized vertical scale for sparklines (like 0-10 s in CheckMK)

_HOST_TABLE_HEADERS: tuple[str, ...] = (
    "Linux host",
    "OS vendor",
    "OS ver.",
    "Agent time",
    "CPU",
    "Load",
    "Cores",
    "Memory",
    "Disk IO",
    "Uptime",
)


@dataclass
class OverviewSnapshot:
    hostname: str
    os_vendor: str
    os_version: str
    os_pretty: str
    n_hosts_up: int
    n_hosts_total: int
    n_svc_ok: int
    n_svc_warn: int
    n_svc_crit: int
    n_svc_total: int
    n_docker_running: int
    load1: float
    load5: float
    load15: float
    host_cpu_pct: float
    host_mem_pct: float
    mem_line: str
    cores: int
    agent_ms: float
    disk_io_str: str
    top_cpu: list[tuple[str, float]] = field(default_factory=list)
    top_mem: list[tuple[str, float]] = field(default_factory=list)
    top_in: list[tuple[str, float]] = field(default_factory=list)  # iface, kbit/s
    top_out: list[tuple[str, float]] = field(default_factory=list)
    top_disk: list[tuple[str, float]] = field(default_factory=list)  # mount, use %
    gateway_line: str = ""
    lan_peer_ips: list[str] = field(default_factory=list)
    uptime: str = ""
    docker_rows: list[tuple[str, str, str, str, str]] = field(default_factory=list)


def _clear_box(box: Gtk.Box) -> None:
    while True:
        c = box.get_first_child()
        if c is None:
            break
        box.remove(c)


def _jiffies_idle_total(line: str) -> tuple[int, int] | None:
    if not line.startswith("cpu "):
        return None
    parts = line.split()
    if len(parts) < 8:
        return None
    nums = [int(x) for x in parts[1:8]]
    idle = nums[3] + nums[4]
    total = sum(nums)
    busy = total - idle
    return busy, total


def _host_cpu_pct_between_samples(ex: HostExecutor) -> float:
    r1 = ex.run_sync(["bash", "-c", "head -1 /proc/stat"], timeout=5.0)
    if not r1.success:
        return 0.0
    a = _jiffies_idle_total(r1.stdout.strip())
    if a is None:
        return 0.0
    busy1, tot1 = a
    time.sleep(0.28)
    r2 = ex.run_sync(["bash", "-c", "head -1 /proc/stat"], timeout=5.0)
    if not r2.success:
        return 0.0
    b = _jiffies_idle_total(r2.stdout.strip())
    if b is None:
        return 0.0
    busy2, tot2 = b
    db = busy2 - busy1
    dt = tot2 - tot1
    if dt <= 0:
        return 0.0
    return max(0.0, min(100.0, 100.0 * db / dt))


def _parse_mem_pct(ex: HostExecutor) -> tuple[float, str]:
    r = ex.run_sync(["free", "-b"], timeout=8.0)
    if not r.success or not r.stdout:
        return 0.0, ""
    for line in r.stdout.splitlines():
        if not line.startswith("Mem:"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        try:
            total = int(parts[1])
            avail = int(parts[6]) if len(parts) > 6 else int(parts[3])
        except ValueError:
            continue
        if total <= 0:
            continue
        used = total - avail
        pct = 100.0 * used / total
        gb_u = used / (1024**3)
        gb_t = total / (1024**3)
        return max(0.0, min(100.0, pct)), f"{gb_u:.1f} / {gb_t:.1f} GiB"
    return 0.0, ""


def _parse_os_pretty(ex: HostExecutor) -> str:
    r = ex.run_sync(["bash", "-c", "grep ^PRETTY_NAME= /etc/os-release 2>/dev/null | head -1"], timeout=5.0)
    if not r.success or not r.stdout.strip():
        return "Linux"
    m = re.match(r'PRETTY_NAME="([^"]+)"', r.stdout.strip())
    if m:
        return m.group(1)
    return r.stdout.strip().split("=", 1)[-1].strip().strip('"')


def _parse_os_vendor_version(ex: HostExecutor) -> tuple[str, str]:
    r = ex.run_sync(["bash", "-c", "cat /etc/os-release 2>/dev/null"], timeout=5.0)
    if not r.success:
        return "Linux", ""
    vendor = ""
    version = ""
    for line in r.stdout.splitlines():
        if line.startswith("NAME="):
            vendor = line.split("=", 1)[-1].strip().strip('"')
        if line.startswith("VERSION_ID="):
            version = line.split("=", 1)[-1].strip().strip('"')
    return vendor or "Linux", version


def _parse_load(ex: HostExecutor) -> tuple[float, float, float]:
    r = ex.run_sync(["bash", "-c", "cat /proc/loadavg 2>/dev/null"], timeout=5.0)
    if not r.success or not r.stdout.strip():
        return 0.0, 0.0, 0.0
    parts = r.stdout.split()
    if len(parts) < 3:
        return 0.0, 0.0, 0.0
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError:
        return 0.0, 0.0, 0.0


def _parse_cores(ex: HostExecutor) -> int:
    r = ex.run_sync(["nproc"], timeout=5.0)
    if r.success and r.stdout.strip().isdigit():
        return max(1, int(r.stdout.strip()))
    return 1


def _parse_uptime(ex: HostExecutor) -> str:
    # Try uptime -p for "up 2 days, 4 hours"
    r = ex.run_sync(["uptime", "-p"], timeout=5.0)
    if r.success and r.stdout.strip():
        return r.stdout.strip().replace("up ", "")
    # Fallback to /proc/uptime
    r = ex.run_sync(["cat", "/proc/uptime"], timeout=5.0)
    if r.success and r.stdout.strip():
        try:
            seconds = float(r.stdout.split()[0])
            days = int(seconds // 86400)
            hours = int((seconds % 86400) // 3600)
            mins = int((seconds % 3600) // 60)
            if days > 0:
                return f"{days} d, {hours} h"
            return f"{hours} h, {mins} m"
        except (ValueError, IndexError):
            pass
    return "unknown"


def _count_running_systemd(ex: HostExecutor) -> int:
    r = ex.run_sync(
        [
            "systemctl",
            "list-units",
            "--type=service",
            "--state=running",
            "--no-pager",
            "--no-legend",
            "-o",
            "json",
        ],
        timeout=60.0,
    )
    if not r.success or not r.stdout.strip():
        return 0
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return 0
    if not isinstance(data, list):
        return 0
    return sum(1 for e in data if isinstance(e, dict) and str(e.get("unit", "")).endswith(".service"))


def _count_failed_units(ex: HostExecutor) -> int:
    r = ex.run_sync(["systemctl", "--failed", "--no-legend", "--no-pager"], timeout=25.0)
    if not r.success or not r.stdout.strip():
        return 0
    n = 0
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("UNIT"):
            continue
        if ".service" in line or ".mount" in line:
            n += 1
    return n


def _parse_ps_top(ex: HostExecutor, sort_col: str) -> list[tuple[str, float]]:
    r = ex.run_sync(
        [
            "bash",
            "-c",
            f"ps --no-headers -eo comm,{sort_col} --sort=-{sort_col} 2>/dev/null | head -10",
        ],
        timeout=12.0,
    )
    if not r.success or not r.stdout.strip():
        return []
    rows: list[tuple[str, float]] = []
    for line in r.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.rsplit(None, 1)
        if len(parts) != 2:
            continue
        name, pct_s = parts
        try:
            pct = float(pct_s)
        except ValueError:
            continue
        name = name.strip()[:40] or "?"
        rows.append((name, max(0.0, min(100.0, pct))))
    return rows


def _parse_proc_net_dev(content: str) -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    for line in content.splitlines():
        if ":" not in line or "|" in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        if not iface or iface == "lo":
            continue
        parts = rest.split()
        if len(parts) < 16:
            continue
        try:
            rx = int(parts[0])
            tx = int(parts[8])
        except ValueError:
            continue
        out[iface] = (rx, tx)
    return out


def _net_top_in_out(ex: HostExecutor) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    r1 = ex.run_sync(["bash", "-c", "cat /proc/net/dev"], timeout=6.0)
    if not r1.success:
        return [], []
    a = _parse_proc_net_dev(r1.stdout)
    time.sleep(0.82)
    r2 = ex.run_sync(["bash", "-c", "cat /proc/net/dev"], timeout=6.0)
    if not r2.success:
        return [], []
    b = _parse_proc_net_dev(r2.stdout)
    dt = 0.82
    rx_rates: list[tuple[str, float]] = []
    tx_rates: list[tuple[str, float]] = []
    for iface in set(a) | set(b):
        arx, atx = a.get(iface, (0, 0))
        brx, btx = b.get(iface, (0, 0))
        drx = max(0, brx - arx)
        dtx = max(0, btx - atx)
        rx_kbps = (drx * 8 / 1000) / dt
        tx_kbps = (dtx * 8 / 1000) / dt
        rx_rates.append((iface, rx_kbps))
        tx_rates.append((iface, tx_kbps))
    rx_rates.sort(key=lambda x: -x[1])
    tx_rates.sort(key=lambda x: -x[1])
    return rx_rates[:10], tx_rates[:10]


def _diskstats_kb_s(ex: HostExecutor) -> str:
    def sample() -> int:
        r = ex.run_sync(
            ["bash", "-c", "awk '{s+=$6+$10} END{print s+0}' /proc/diskstats"],
            timeout=6.0,
        )
        if not r.success:
            return 0
        try:
            return int(float(r.stdout.strip() or 0))
        except ValueError:
            return 0

    s1 = sample()
    time.sleep(0.75)
    s2 = sample()
    ds = max(0, s2 - s1)
    kb_s = (ds * 512) / 1024 / 0.75
    if kb_s < 1:
        return f"{kb_s * 1024:.1f} B/s"
    return f"{kb_s:.1f} KB/s"


def _df_mounts(ex: HostExecutor) -> list[tuple[str, float, str]]:
    r = ex.run_sync(
        [
            "bash",
            "-c",
            "df -PB1 --output=target,pcent,used --exclude-type=tmpfs "
            "--exclude-type=devtmpfs --exclude-type=squashfs 2>/dev/null | tail -n +2",
        ],
        timeout=15.0,
    )
    if not r.success or not r.stdout.strip():
        return []
    rows: list[tuple[str, float, str]] = []
    for line in r.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        target, pcent_s, used_s = parts[0], parts[1], parts[2]
        m = re.match(r"(\d+)%", pcent_s)
        if not m:
            continue
        try:
            pct = float(m.group(1))
            used_b = int(used_s)
        except ValueError:
            continue
        gib = used_b / (1024**3)
        rows.append((target, pct, f"{gib:.2f} GiB"))
    rows.sort(key=lambda x: -x[1])
    return rows[:12]


def _default_route_line(ex: HostExecutor) -> str:
    r = ex.run_sync(["bash", "-c", "ip route show default 2>/dev/null | head -n1"], timeout=5.0)
    if r.success and r.stdout.strip():
        return " ".join(r.stdout.strip().split())
    return ""


def _local_own_ips(ex: HostExecutor) -> set[str]:
    r = ex.run_sync(["bash", "-c", "hostname -I 2>/dev/null"], timeout=4.0)
    if not r.success or not r.stdout.strip():
        return set()
    return {x.strip() for x in r.stdout.split() if x.strip()}


def _reachable_neighbor_ips(ex: HostExecutor) -> list[str]:
    """IPs in REACHABLE state (typical LAN / same L2 as your internet-facing path)."""
    r = ex.run_sync(
        [
            "bash",
            "-c",
            r"ip neigh show 2>/dev/null | awk '/REACHABLE/ {print $1}'",
        ],
        timeout=8.0,
    )
    if not r.success or not r.stdout.strip():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for line in r.stdout.strip().splitlines():
        ip = (line.strip().split() or [""])[0]
        if not ip or ip in seen:
            continue
        seen.add(ip)
        out.append(ip)
    return out


def _docker_stats_rows(ex: HostExecutor) -> tuple[int, list[tuple[str, str, str, str, str]]]:
    # Stats for CPU/Mem
    r = ex.run_sync(
        [
            "docker", "stats", "--no-stream",
            "--format", "{{.Name}}\t{{.CPUPerc}}\t{{.MemPerc}}\t{{.MemUsage}}",
        ],
        timeout=45.0,
    )
    # PS for Uptime
    rps = ex.run_sync(
        ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
        timeout=15.0,
    )

    ps_map: dict[str, str] = {}
    if rps.success and rps.stdout.strip():
        for line in rps.stdout.strip().splitlines():
            pts = line.split("\t")
            if len(pts) == 2:
                ps_map[pts[0].strip()] = pts[1].strip().replace("Up ", "")

    if not r.success or not r.stdout.strip():
        return len(ps_map), []

    out: list[tuple[str, str, str, str, str]] = []
    for line in r.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            name = parts[0].strip()
            upt = ps_map.get(name, "running")
            out.append((name, parts[1].strip(), parts[2].strip(), parts[3].strip(), upt))
        elif len(parts) == 1 and parts[0].strip():
            name = parts[0].strip()
            upt = ps_map.get(name, "running")
            out.append((name, "", "", "", upt))

    return len(out), out


def collect_snapshot(ex: HostExecutor | None = None) -> OverviewSnapshot:
    t0 = time.perf_counter()
    ex = ex or HostExecutor()
    hn = ex.run_sync(["hostname", "-f"], timeout=4.0)
    fqdn = hn.stdout.strip() if hn.success and hn.stdout.strip() else socket.gethostname()
    vendor, version = _parse_os_vendor_version(ex)
    os_pretty = _parse_os_pretty(ex)
    n_sys = _count_running_systemd(ex)
    n_fail = _count_failed_units(ex)
    n_dock, dock_rows = _docker_stats_rows(ex)
    load1, load5, load15 = _parse_load(ex)
    cpu_pct = _host_cpu_pct_between_samples(ex)
    mem_pct, mem_line = _parse_mem_pct(ex)
    uptime = _parse_uptime(ex)
    top_in, top_out = _net_top_in_out(ex)
    disk_io = _diskstats_kb_s(ex)
    df_rows = _df_mounts(ex)
    top_disk = [(t, pct) for (t, pct, _) in df_rows]
    gateway_line = _default_route_line(ex)
    own_ips = _local_own_ips(ex)
    lan_peer_ips = [ip for ip in _reachable_neighbor_ips(ex) if ip not in own_ips][:48]
    t1 = time.perf_counter()
    agent_ms = (t1 - t0) * 1000.0
    ok = n_sys
    warn = n_fail
    crit = 0
    total_svc = max(1, ok + warn + crit)
    n_neigh = len(lan_peer_ips)
    return OverviewSnapshot(
        hostname=fqdn,
        os_vendor=vendor,
        os_version=version,
        os_pretty=os_pretty,
        n_hosts_up=1,
        n_hosts_total=1 + n_neigh,
        n_svc_ok=ok,
        n_svc_warn=warn,
        n_svc_crit=crit,
        n_svc_total=max(1, total_svc),
        n_docker_running=n_dock,
        load1=load1,
        load5=load5,
        load15=load15,
        host_cpu_pct=cpu_pct,
        host_mem_pct=mem_pct,
        mem_line=mem_line,
        cores=_parse_cores(ex),
        agent_ms=agent_ms,
        disk_io_str=disk_io,
        top_disk=top_disk,
        gateway_line=gateway_line,
        lan_peer_ips=lan_peer_ips,
        uptime=uptime,
        top_cpu=_parse_ps_top(ex, "%cpu"),
        top_mem=_parse_ps_top(ex, "%mem"),
        top_in=top_in,
        top_out=top_out,
        docker_rows=dock_rows,
    )


def _dashboard_card() -> Gtk.Box:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    card.add_css_class("servers-dashboard-card")
    card.set_hexpand(True)
    return card


def _metric_row(name: str, value_0_100: float, value_label: str, *, bar_class: str = "") -> Gtk.Box:
    row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
    row.add_css_class("servers-topn-row")
    top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    nl = Gtk.Label(label=name)
    nl.set_hexpand(True)
    nl.set_xalign(0.0)
    nl.set_ellipsize(Pango.EllipsizeMode.END)
    nl.add_css_class("caption")
    vl = Gtk.Label(label=value_label)
    vl.set_xalign(1.0)
    vl.add_css_class("numeric")
    vl.add_css_class("caption")
    top.append(nl)
    top.append(vl)
    row.append(top)
    bar = Gtk.LevelBar.new_for_interval(0.0, 100.0)
    bar.set_mode(Gtk.LevelBarMode.CONTINUOUS)
    bar.set_value(min(100.0, max(0.0, value_0_100)))
    bar.add_css_class("servers-level-bar")
    if bar_class:
        bar.add_css_class(bar_class)
    bar.set_hexpand(True)
    row.append(bar)
    return row


def _top_n_column(title: str) -> tuple[Gtk.Box, Gtk.Box]:
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    outer.add_css_class("servers-dashboard-card")
    outer.set_hexpand(True)
    outer.set_size_request(0, -1)
    tl = Gtk.Label(label=title)
    tl.add_css_class("title-4")
    tl.set_wrap(True)
    tl.set_xalign(0.0)
    outer.append(tl)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    outer.append(body)
    return outer, body


def _triple_line_chart(series: dict[str, list[float]]) -> Gtk.DrawingArea:
    da = Gtk.DrawingArea()
    da.set_content_width(200)
    da.set_content_height(72)
    da.set_hexpand(True)

    def on_draw(_w: Gtk.DrawingArea, cr: Any, width: int, height: int) -> None:
        cr.save()
        cr.set_source_rgba(0.1, 0.11, 0.13, 1.0)
        cr.rectangle(0, 0, width, height)
        cr.fill()
        load_v = list(series.get("load", []))[-40:]
        cpu_v = list(series.get("cpu", []))[-40:]
        mem_v = list(series.get("mem", []))[-40:]
        n = max(len(load_v), len(cpu_v), len(mem_v))
        if n < 2:
            cr.restore()
            return
        pad = 4.0
        w_i = width - 2 * pad
        h_i = height - 2 * pad

        def y_norm(vals: list[float], i: int) -> float:
            v = vals[i] if i < len(vals) else vals[-1]
            return h_i - h_i * min(1.0, float(v) / CHART_Y)

        def stroke(vals: list[float], rgba: tuple[float, float, float, float]) -> None:
            if len(vals) < 2:
                return
            cr.set_source_rgba(*rgba)
            cr.set_line_width(1.6)
            cr.move_to(pad, pad + y_norm(vals, 0))
            for i in range(1, len(vals)):
                xi = pad + w_i * (i / max(1, len(vals) - 1))
                yi = pad + y_norm(vals, i)
                cr.line_to(xi, yi)
            cr.stroke()

        stroke(load_v, (0.25, 0.88, 0.45, 1.0))
        stroke([min(CHART_Y, c / 10.0) for c in cpu_v], (0.35, 0.65, 1.0, 1.0))
        stroke([min(CHART_Y, m / 10.0) for m in mem_v], (0.95, 0.75, 0.25, 1.0))
        cr.restore()

    da.set_draw_func(on_draw)
    return da


def _empty_placeholder(msg: str = "No entries") -> Gtk.Label:
    ph = Gtk.Label(label=msg)
    ph.add_css_class("dim-label")
    ph.set_xalign(0.0)
    return ph


def _hosts_grid_clear(grid: Gtk.Grid) -> None:
    while True:
        c = grid.get_first_child()
        if c is None:
            break
        grid.remove(c)


def _table_data_lbl(text: str) -> Gtk.Label:
    lab = Gtk.Label(label=text)
    lab.set_xalign(0.0)
    lab.set_hexpand(True)
    lab.set_ellipsize(Pango.EllipsizeMode.END)
    lab.set_wrap(True)
    lab.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
    lab.add_css_class("caption")
    lab.add_css_class("servers-table-cell")
    return lab


def _cell_bar_pct(pct: float, text: str) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.add_css_class("servers-table-cell")
    box.set_valign(Gtk.Align.CENTER)
    bar = Gtk.LevelBar.new_for_interval(0.0, 100.0)
    bar.set_value(min(100.0, max(0.0, pct)))
    bar.add_css_class("servers-level-bar")
    bar.add_css_class("servers-level-bar-table")
    bar.set_size_request(72, -1)
    lbl = Gtk.Label(label=text)
    lbl.add_css_class("caption")
    lbl.set_xalign(0.0)
    lbl.set_valign(Gtk.Align.CENTER)
    box.append(bar)
    box.append(lbl)
    return box


def _host_table_attach_row(
    grid: Gtk.Grid,
    row: int,
    *,
    host: str,
    vendor: str,
    version: str,
    agent_ms: str,
    cpu_widget: Gtk.Widget,
    load_s: str,
    cores_s: str,
    mem_widget: Gtk.Widget,
    disk_io: str,
    uptime_s: str,
) -> None:
    grid.attach(_table_data_lbl(host), 0, row, 1, 1)
    grid.attach(_table_data_lbl(vendor), 1, row, 1, 1)
    grid.attach(_table_data_lbl(version), 2, row, 1, 1)
    grid.attach(_table_data_lbl(agent_ms), 3, row, 1, 1)
    grid.attach(cpu_widget, 4, row, 1, 1)
    grid.attach(_table_data_lbl(load_s), 5, row, 1, 1)
    grid.attach(_table_data_lbl(cores_s), 6, row, 1, 1)
    grid.attach(mem_widget, 7, row, 1, 1)
    grid.attach(_table_data_lbl(disk_io), 8, row, 1, 1)
    grid.attach(_table_data_lbl(uptime_s), 9, row, 1, 1)


def _rebuild_hosts_table(grid: Gtk.Grid, snap: OverviewSnapshot) -> None:
    _hosts_grid_clear(grid)
    for col, title in enumerate(_HOST_TABLE_HEADERS):
        hl = Gtk.Label(label=title)
        hl.set_xalign(0.0)
        hl.set_hexpand(True)
        hl.set_wrap(True)
        hl.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        hl.add_css_class("caption")
        hl.add_css_class("servers-table-header-cell")
        grid.attach(hl, col, 0, 1, 1)

    row = 1
    cpu_w = _cell_bar_pct(snap.host_cpu_pct, f"{snap.host_cpu_pct:.1f}%")
    mem_w = _cell_bar_pct(snap.host_mem_pct, f"{snap.host_mem_pct:.1f}%")
    _host_table_attach_row(
        grid,
        row,
        host=snap.hostname,
        vendor=snap.os_vendor,
        version=snap.os_version,
        agent_ms=f"{snap.agent_ms:.0f} ms",
        cpu_widget=cpu_w,
        load_s=f"{snap.load1:.2f}",
        cores_s=str(snap.cores),
        mem_widget=mem_w,
        disk_io=snap.disk_io_str,
        uptime_s=snap.uptime,
    )
    row += 1

    for name, cpu_s, mem_s, mem_u, upt in snap.docker_rows[:20]:
        cpu_pct_s = (cpu_s or "").rstrip("%")
        mem_pct_s = (mem_s or "").rstrip("%")
        try:
            cpv = float(cpu_pct_s) if cpu_pct_s else 0.0
        except ValueError:
            cpv = 0.0
        try:
            mpv = float(mem_pct_s) if mem_pct_s else 0.0
        except ValueError:
            mpv = 0.0
        _host_table_attach_row(
            grid,
            row,
            host=name,
            vendor="Container",
            version="—",
            agent_ms="—",
            cpu_widget=_cell_bar_pct(cpv, cpu_s or "—"),
            load_s="—",
            cores_s="—",
            mem_widget=_cell_bar_pct(mpv, mem_s or "—"),
            disk_io=mem_u or "—",
            uptime_s=upt,
        )
        row += 1

    for ip in snap.lan_peer_ips[:32]:
        _host_table_attach_row(
            grid,
            row,
            host=ip,
            vendor="LAN neighbor",
            version="REACHABLE",
            agent_ms="—",
            cpu_widget=_table_data_lbl("—"),
            load_s="—",
            cores_s="—",
            mem_widget=_table_data_lbl("—"),
            disk_io="LAN link",
            uptime_s="neighbor",
        )
        row += 1


class WorkstationServersOverviewPanel(Gtk.Box):
    """CheckMK-style Linux hosts overview (local machine)."""

    def __init__(
        self,
        *,
        parent_stack: Gtk.Stack,
        shrink_for_embedding: bool = False,
        **kw: Any,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0, **kw)
        self._parent_stack = parent_stack
        self._busy = False
        self._poll_id = 0
        self._chart_series: dict[str, list[float]] = {"load": [], "cpu": [], "mem": []}

        self._card_host_summary: Gtk.Label | None = None
        self._card_svc_summary: Gtk.Label | None = None
        self._load_chart: Gtk.DrawingArea | None = None
        self._load_big: Gtk.Label | None = None
        self._chart_caption: Gtk.Label | None = None

        self._col_cpu_body: Gtk.Box | None = None
        self._col_mem_body: Gtk.Box | None = None
        self._col_in_body: Gtk.Box | None = None
        self._col_out_body: Gtk.Box | None = None
        self._col_disk_body: Gtk.Box | None = None
        self._hosts_grid: Gtk.Grid | None = None

        # When embedded in a page that already has a vertical Gtk.ScrolledWindow
        # (e.g. SystemMonitorPage), do NOT wrap this block in another vertical
        # ScrolledWindow — nested scroll + vexpand prevents the outer view from
        # scrolling. Append ``root`` directly so one scrollbar owns the document.
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        root.set_margin_start(12)
        root.set_margin_end(12)
        root.set_margin_top(10)
        root.set_margin_bottom(12)

        if not shrink_for_embedding:
            title = Gtk.Label(label="Monitor · Overview · Linux hosts")
            title.add_css_class("title-2")
            title.set_xalign(0.0)
            root.append(title)
            sub = Gtk.Label(
                label=(
                    "This machine, Docker containers, default route to the internet, "
                    "and REACHABLE neighbors on the same LAN / link."
                ),
            )
            sub.add_css_class("dim-label")
            sub.set_wrap(True)
            sub.set_xalign(0.0)
            root.append(sub)

        left_scroll: Gtk.ScrolledWindow | None = None
        if not shrink_for_embedding:
            left_scroll = Gtk.ScrolledWindow(
                hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                vexpand=True,
                hexpand=True,
            )

        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        top.set_homogeneous(False)

        c1 = _dashboard_card()
        led = Gtk.Label(label="●")
        led.add_css_class("servers-status-led")
        led.set_valign(Gtk.Align.START)
        h1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        h1.append(led)
        v1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        t1 = Gtk.Label(label="Host statistics")
        t1.add_css_class("servers-dashboard-card-title")
        t1.set_xalign(0.0)
        self._card_host_summary = Gtk.Label(label="<i>Connecting to host...</i>")
        self._card_host_summary.set_xalign(0.0)
        self._card_host_summary.set_use_markup(True)
        self._card_host_summary.set_wrap(True)
        self._card_host_summary.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        self._card_host_summary.set_max_width_chars(56)
        self._card_host_summary.add_css_class("servers-dashboard-stat")
        v1.append(t1)
        v1.append(self._card_host_summary)
        h1.append(v1)
        c1.append(h1)
        top.append(c1)

        c2 = _dashboard_card()
        t2 = Gtk.Label(label="Service statistics")
        t2.add_css_class("servers-dashboard-card-title")
        t2.set_xalign(0.0)
        self._card_svc_summary = Gtk.Label(label="<i>Initializing metrics...</i>")
        self._card_svc_summary.set_xalign(0.0)
        self._card_svc_summary.set_use_markup(True)
        self._card_svc_summary.set_wrap(True)
        self._card_svc_summary.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        self._card_svc_summary.set_max_width_chars(56)
        self._card_svc_summary.add_css_class("servers-dashboard-stat")
        c2.append(t2)
        c2.append(self._card_svc_summary)
        top.append(c2)

        c3 = _dashboard_card()
        t3 = Gtk.Label(label="Host metrics (sample)")
        t3.add_css_class("servers-dashboard-card-title")
        t3.set_xalign(0.0)
        c3.append(t3)
        self._load_big = Gtk.Label(label="<i>Waiting for first sample...</i>")
        self._load_big.set_xalign(0.0)
        self._load_big.set_use_markup(True)
        self._load_big.add_css_class("servers-dashboard-stat")
        c3.append(self._load_big)
        self._load_chart = _triple_line_chart(self._chart_series)
        c3.append(self._load_chart)
        self._chart_caption = Gtk.Label(
            label="Green: load 1m · Blue: CPU % / 10 · Yellow: Mem % / 10",
        )
        self._chart_caption.add_css_class("dim-label")
        self._chart_caption.set_xalign(0.0)
        c3.append(self._chart_caption)
        top.append(c3)
        root.append(top)

        flow = Gtk.FlowBox()
        flow.set_max_children_per_line(3)
        flow.set_row_spacing(10)
        flow.set_column_spacing(10)
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_homogeneous(False)

        o_cpu, b_cpu = _top_n_column("Top 10: CPU utilization")
        o_mem, b_mem = _top_n_column("Top 10: Memory utilization")
        o_in, b_in = _top_n_column("Top 10: Input bandwidth")
        o_out, b_out = _top_n_column("Top 10: Output bandwidth")
        o_dk, b_dk = _top_n_column("Top 10: Disk utilization")
        self._col_cpu_body = b_cpu
        self._col_mem_body = b_mem
        self._col_in_body = b_in
        self._col_out_body = b_out
        self._col_disk_body = b_dk
        for w in (o_cpu, o_mem, o_in, o_out, o_dk):
            flow.append(w)
        root.append(flow)

        tbl_title = Gtk.Label(label="Hosts, containers & LAN neighbors")
        tbl_title.add_css_class("title-3")
        tbl_title.set_xalign(0.0)
        tbl_title.set_wrap(True)
        tbl_title.set_natural_wrap_mode(Gtk.NaturalWrapMode.WORD)
        root.append(tbl_title)

        table_scroll = Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=False,
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        table_scroll.add_css_class("servers-table-scroll")
        self._hosts_grid = Gtk.Grid(column_spacing=10, row_spacing=4)
        self._hosts_grid.add_css_class("servers-host-table")
        self._hosts_grid.add_css_class("servers-table-body")
        table_scroll.set_child(self._hosts_grid)
        root.append(table_scroll)

        if left_scroll is not None:
            left_scroll.set_child(root)
            self.append(left_scroll)
        else:
            self.append(root)

        self._visibility_handler = self._parent_stack.connect(
            "notify::visible-child", self._on_visibility
        )
        # Ensure we start polling if we are the initial visible child
        GLib.idle_add(self._on_visibility)

    def do_unrealize(self) -> None:
        self._stop_poll()
        if getattr(self, "_visibility_handler", 0):
            self._parent_stack.disconnect(self._visibility_handler)
            self._visibility_handler = 0
        Gtk.Box.do_unrealize(self)

    def _visible(self) -> bool:
        return self._parent_stack.get_visible_child() is self

    def _on_visibility(self, *_args: Any) -> None:
        if self._visible():
            self._start_poll()
            self._kick_refresh()
        else:
            self._stop_poll()

    def _start_poll(self) -> None:
        if self._poll_id:
            return
        self._poll_id = GLib.timeout_add_seconds(_POLL_SECONDS, self._on_tick)

    def _stop_poll(self) -> None:
        if self._poll_id:
            GLib.source_remove(self._poll_id)
            self._poll_id = 0

    def _on_tick(self) -> bool:
        if not self._visible():
            self._poll_id = 0
            return False
        self._kick_refresh()
        return True

    def _kick_refresh(self) -> None:
        if self._busy:
            return
        self._busy = True

        def work() -> None:
            try:
                snap = collect_snapshot()
            except Exception:
                log.exception("servers overview snapshot failed")
                snap = None
            GLib.idle_add(self._apply, snap)

        _bg(work)

    def _apply(self, snap: OverviewSnapshot | None) -> bool:
        self._busy = False
        if snap is None:
            if self._card_host_summary:
                self._card_host_summary.set_markup(
                    "<span color='#ef4444'>● Collection failed.</span>\n"
                    "<small>Check project logs for details.</small>"
                )
            return False

        self._chart_series.setdefault("load", []).append(min(CHART_Y, snap.load1))
        self._chart_series.setdefault("cpu", []).append(snap.host_cpu_pct)
        self._chart_series.setdefault("mem", []).append(snap.host_mem_pct)
        for k in self._chart_series:
            if len(self._chart_series[k]) > 48:
                self._chart_series[k] = self._chart_series[k][-48:]

        esc_h = GLib.markup_escape_text(snap.hostname)
        esc_gw = GLib.markup_escape_text(snap.gateway_line or "(no default route)")
        n_neigh = len(snap.lan_peer_ips)
        if self._card_host_summary:
            nd = len(snap.docker_rows)
            self._card_host_summary.set_markup(
                f"<b>{snap.n_hosts_up}</b> monitored host · <b>{n_neigh}</b> LAN neighbor"
                f"{'s' if n_neigh != 1 else ''} · <b>{nd}</b> Docker row"
                f"{'s' if nd != 1 else ''}\n"
                f"<small>{esc_h}</small>\n"
                f"<small>Internet path: {esc_gw}</small>",
            )
        if self._card_svc_summary:
            self._card_svc_summary.set_markup(
                f"<b>{snap.n_svc_ok}</b> OK · <b>{snap.n_svc_warn}</b> Warning · "
                f"<b>{snap.n_svc_crit}</b> Critical\n"
                f"<small>{snap.n_svc_total} units · {snap.n_docker_running} containers</small>",
            )
        if self._load_big:
            self._load_big.set_label(
                f"Load {snap.load1:.2f} / {snap.load5:.2f} / {snap.load15:.2f} · poll {snap.agent_ms:.0f} ms",
            )
        if self._load_chart:
            self._load_chart.queue_draw()

        mx_cpu = max((x[1] for x in snap.top_cpu), default=1.0) or 1.0
        mx_mem = max((x[1] for x in snap.top_mem), default=1.0) or 1.0
        mx_in = max((x[1] for x in snap.top_in), default=1.0) or 1.0
        mx_out = max((x[1] for x in snap.top_out), default=1.0) or 1.0

        if self._col_cpu_body:
            _clear_box(self._col_cpu_body)
            if snap.top_cpu:
                for name, pct in snap.top_cpu:
                    self._col_cpu_body.append(
                        _metric_row(name, 100.0 * pct / mx_cpu, f"{pct:.1f}%"),
                    )
            else:
                self._col_cpu_body.append(_empty_placeholder())

        if self._col_mem_body:
            _clear_box(self._col_mem_body)
            if snap.top_mem:
                for name, pct in snap.top_mem:
                    self._col_mem_body.append(
                        _metric_row(
                            name,
                            100.0 * pct / mx_mem,
                            f"{pct:.1f}%",
                            bar_class="servers-level-bar-mem",
                        ),
                    )
            else:
                self._col_mem_body.append(_empty_placeholder())

        if self._col_in_body:
            _clear_box(self._col_in_body)
            filled_in = False
            if snap.top_in:
                for iface, kb in snap.top_in:
                    if kb < 0.01:
                        continue
                    filled_in = True
                    self._col_in_body.append(
                        _metric_row(
                            iface,
                            100.0 * kb / mx_in,
                            f"{kb:.1f} kbit/s",
                            bar_class="servers-level-bar-in",
                        ),
                    )
            if not filled_in:
                self._col_in_body.append(_empty_placeholder())

        if self._col_out_body:
            _clear_box(self._col_out_body)
            filled_out = False
            if snap.top_out:
                for iface, kb in snap.top_out:
                    if kb < 0.01:
                        continue
                    filled_out = True
                    self._col_out_body.append(
                        _metric_row(
                            iface,
                            100.0 * kb / mx_out,
                            f"{kb:.1f} kbit/s",
                            bar_class="servers-level-bar-out",
                        ),
                    )
            if not filled_out:
                self._col_out_body.append(_empty_placeholder())

        if self._col_disk_body:
            _clear_box(self._col_disk_body)
            mx_disk = max((x[1] for x in snap.top_disk), default=1.0) or 1.0
            if snap.top_disk:
                for mnt, pct in snap.top_disk:
                    self._col_disk_body.append(
                        _metric_row(
                            mnt[:28],
                            100.0 * pct / mx_disk,
                            f"{pct:.1f}%",
                            bar_class="servers-level-bar-disk",
                        ),
                    )
            else:
                self._col_disk_body.append(_empty_placeholder())

        if self._hosts_grid is not None:
            _rebuild_hosts_table(self._hosts_grid, snap)

        return False

    def reset_subsections(self) -> None:
        self._stop_poll()
