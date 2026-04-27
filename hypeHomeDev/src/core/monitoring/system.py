"""HypeDevHome — Background system resource monitor.

Collects CPU, Memory, and Swap data using ``psutil`` and emits
events via the global ``EventBus``.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any

import psutil

from core.events import EventBus

log = logging.getLogger(__name__)


class SystemMonitor:
    """Thread-safe background monitor for system resources.

    Publishes periodic updates to the EventBus:
    - ``sysmon.cpu``: {'total_percent': float, 'core_percents': list[float]}
    - ``sysmon.memory``: {'used': float, 'total': float, 'percent': float}
    - ``sysmon.swap``: {'used': float, 'total': float, 'percent': float}
    """

    def __init__(self, event_bus: EventBus, interval: float = 2.0) -> None:
        """Initialize the monitor.

        Args:
            event_bus: The application event bus to publish to.
            interval: Polling internal in seconds.
        """
        self._event_bus = event_bus
        self._interval = interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # For network speed calculation (aggregate fallback)
        self._last_net_time: float | None = None
        self._last_dl_bytes: float = 0
        self._last_ul_bytes: float = 0
        # Per-interface: iface -> (timestamp, bytes_recv, bytes_sent)
        self._last_net_per_nic: dict[str, tuple[float, float, float]] = {}
        # Public IP (fetched in monitor thread; cached)
        self._public_ip_cache: str = ""
        self._public_ip_cache_time: float = 0.0

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                log.warning("SystemMonitor is already running")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, name="SystemMonitor", daemon=True)
            self._thread.start()
            log.info("SystemMonitor started (interval=%fs)", self._interval)

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        with self._lock:
            if not self._thread:
                return

            self._stop_event.set()
            # We don't join here to avoid blocking the caller (usually UI thread)
            # but we set the reference to None.
            self._thread = None
            log.info("SystemMonitor stopping...")

    def _run(self) -> None:
        """Main loop running in the background thread."""
        # Initial call to psutil.cpu_percent with interval=None initializes the timer
        try:
            psutil.cpu_percent(interval=None)
        except Exception:
            log.warning("Failed to initialize psutil CPU timer")

        while not self._stop_event.is_set():
            try:
                self._collect_and_emit()
            except Exception:
                log.exception("Error during system data collection")
                # Don't crash on errors, just continue
                # Wait a bit longer after an error
                self._stop_event.wait(min(self._interval * 2, 10.0))
                continue

            # Sleep in increments to remain responsive to stop_event
            self._stop_event.wait(self._interval)

    def _collect_and_emit(self) -> None:
        """Perform a single collection cycle and publish events."""
        try:
            # CPU Info
            # interval=None here returns the % since last call
            cpu_total = psutil.cpu_percent(interval=None)
            cpu_cores = psutil.cpu_percent(interval=None, percpu=True)

            # Get CPU frequency
            cpu_freq = psutil.cpu_freq()
            freq_mhz = cpu_freq.current if cpu_freq else 0

            # Get load average
            load_avg = psutil.getloadavg()
            cpu_temp = self._get_cpu_temperature()

            self._event_bus.emit(
                "sysmon.cpu",
                total_percent=cpu_total,
                core_percents=cpu_cores,
                core_count=len(cpu_cores),
                frequency_mhz=freq_mhz,
                load_avg=load_avg,
                temperature_c=cpu_temp,
            )
        except Exception as e:
            log.warning("Failed to collect CPU data: %s", e)
            # Emit empty CPU data to keep UI responsive
            self._event_bus.emit(
                "sysmon.cpu",
                total_percent=0,
                core_percents=[],
                core_count=0,
                frequency_mhz=0,
                load_avg=(0, 0, 0),
                temperature_c=None,
            )

        try:
            # Memory Info
            mem = psutil.virtual_memory()
            # Convert to MB for easier UI handling
            to_mb = 1024 * 1024
            self._event_bus.emit(
                "sysmon.memory",
                used=mem.used / to_mb,
                total=mem.total / to_mb,
                available=mem.available / to_mb,
                percent=mem.percent,
            )

            # Swap Info
            swap = psutil.swap_memory()
            self._event_bus.emit(
                "sysmon.swap",
                used=swap.used / to_mb,
                total=swap.total / to_mb,
                percent=swap.percent,
            )
        except Exception as e:
            log.warning("Failed to collect memory data: %s", e)
            # Emit empty memory data
            self._event_bus.emit(
                "sysmon.memory",
                used=0,
                total=1,
                available=0,
                percent=0,
            )
            self._event_bus.emit(
                "sysmon.swap",
                used=0,
                total=0,
                percent=0,
            )

        try:
            # Network Info (per-interface speeds, public IP, link state)
            self._emit_network_metrics()
        except Exception as e:
            log.warning("Failed to collect network data: %s", e)
            self._event_bus.emit(
                "sysmon.network",
                dl_speed=0.0,
                ul_speed=0.0,
                dl_bytes=0,
                ul_bytes=0,
                local_ip="",
                public_ip="",
                connected=False,
                interfaces=[],
                per_nic={},
            )

        try:
            gpu_data = self._collect_gpu_data()
            if gpu_data:
                self._event_bus.emit("sysmon.gpu", **gpu_data)
            else:
                self._event_bus.emit("sysmon.gpu", **self._empty_gpu_payload())
        except Exception as e:
            log.warning("Failed to collect GPU data: %s", e)
            self._event_bus.emit("sysmon.gpu", **self._empty_gpu_payload())

        log.debug("SystemMonitor: Completed collection cycle")

    def _get_local_ip(self) -> str:
        """Get local IP address (default route heuristic)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return str(ip)
        except Exception:
            return ""

    def _fetch_public_ip_cached(self, max_age_s: float = 300.0) -> str:
        """Return WAN IPv4 with simple HTTP GET; cached in the monitor thread."""
        now = time.time()
        if self._public_ip_cache and (now - self._public_ip_cache_time) < max_age_s:
            return self._public_ip_cache
        for url in (
            "https://api.ipify.org",
            "https://icanhazip.com",
            "https://ifconfig.me/ip",
        ):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "HypeDevHome/1.0"})
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    text = resp.read().decode("utf-8", errors="replace").strip()
                    if text and len(text) < 64:
                        self._public_ip_cache = text.splitlines()[0].strip()
                        self._public_ip_cache_time = now
                        return self._public_ip_cache
            except (urllib.error.URLError, OSError, ValueError) as e:
                log.debug("Public IP fetch failed (%s): %s", url, e)
                continue
        return self._public_ip_cache

    def _network_has_carrier(self) -> bool:
        """True if some non-loopback interface is up with a non-local IPv4."""
        try:
            stats = psutil.net_if_stats()
            addrs = psutil.net_if_addrs()
            for name, st in stats.items():
                if name.startswith("lo"):
                    continue
                if not st.isup:
                    continue
                for addr in addrs.get(name, []):
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        if ip and not ip.startswith("127."):
                            return True
        except Exception:
            pass
        return False

    def _emit_network_metrics(self) -> None:
        """Compute per-NIC I/O, aggregate speeds, public IP; emit sysmon.network."""
        current_time = time.time()
        pernic = psutil.net_io_counters(pernic=True)
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        per_nic: dict[str, dict[str, Any]] = {}
        sum_dl = 0.0
        sum_ul = 0.0
        total_recv = 0
        total_sent = 0

        for name, counters in pernic.items():
            total_recv += counters.bytes_recv
            total_sent += counters.bytes_sent
            prev = self._last_net_per_nic.get(name)
            dl_s = 0.0
            ul_s = 0.0
            if prev is not None:
                t0, r0, s0 = prev
                dt = current_time - t0
                if dt > 0:
                    dl_s = (counters.bytes_recv - r0) / dt
                    ul_s = (counters.bytes_sent - s0) / dt
            self._last_net_per_nic[name] = (
                current_time,
                float(counters.bytes_recv),
                float(counters.bytes_sent),
            )
            st = stats.get(name)
            up = bool(st and st.isup)
            ipv4 = ""
            for a in addrs.get(name, []):
                if a.family == socket.AF_INET and not a.address.startswith("127."):
                    ipv4 = a.address
                    break
            per_nic[name] = {
                "dl_speed": dl_s,
                "ul_speed": ul_s,
                "bytes_recv": counters.bytes_recv,
                "bytes_sent": counters.bytes_sent,
                "isup": up,
                "ipv4": ipv4,
            }
            if not name.startswith("lo"):
                sum_dl += dl_s
                sum_ul += ul_s

        interfaces: list[dict[str, Any]] = []
        for name in sorted(per_nic.keys()):
            if name.startswith("lo"):
                continue
            entry = per_nic[name]
            interfaces.append(
                {
                    "name": name,
                    "ip": entry.get("ipv4") or "",
                    "isup": entry.get("isup", False),
                }
            )

        connected = self._network_has_carrier()
        local_ip = self._get_local_ip()
        public_ip = self._fetch_public_ip_cached() if connected else ""

        self._event_bus.emit(
            "sysmon.network",
            dl_speed=sum_dl,
            ul_speed=sum_ul,
            dl_bytes=total_recv,
            ul_bytes=total_sent,
            local_ip=local_ip,
            public_ip=public_ip,
            connected=connected,
            interfaces=interfaces,
            per_nic=per_nic,
        )

    def _get_cpu_temperature(self) -> float | None:
        """Read CPU temperature from sensors or sysfs."""
        try:
            temps = psutil.sensors_temperatures(fahrenheit=False)
            if temps:
                for entries in temps.values():
                    for entry in entries:
                        label = entry.label.lower() if entry.label else ""
                        if (
                            ("package" in label or "cpu" in label or "core" in label)
                            and entry.current is not None
                            and entry.current > 0
                        ):
                            return float(entry.current)
        except Exception:
            pass

        return self._read_cpu_temp_sysfs()

    def _read_cpu_temp_sysfs(self) -> float | None:
        """Fallback CPU temperature via /sys/class/thermal."""
        try:
            thermal_path = "/sys/class/thermal"
            if os.path.isdir(thermal_path):
                for zone in os.listdir(thermal_path):
                    if zone.startswith("thermal_zone"):
                        type_path = os.path.join(thermal_path, zone, "type")
                        temp_path = os.path.join(thermal_path, zone, "temp")
                        if os.path.exists(type_path) and os.path.exists(temp_path):
                            with open(type_path) as f:
                                zone_type = f.read().strip().lower()
                            if "cpu" in zone_type or "core" in zone_type or "package" in zone_type:
                                with open(temp_path) as f:
                                    temp_value = float(f.read().strip())
                                # Some sensors report millidegrees
                                if temp_value > 1000:
                                    temp_value /= 1000.0
                                return temp_value
        except Exception:
            pass
        return None

    def _empty_gpu_payload(self) -> dict[str, Any]:
        """Default payload when no GPU is available (matches EventBus flat shape)."""
        return {
            "vendor": "Unknown",
            "model": "Unknown",
            "utilization": 0.0,
            "vram_used": 0.0,
            "vram_total": 1.0,
            "temperature_c": None,
            "fan_speed": None,
            "detected": False,
            "gpus": [],
            "gpu_count": 0,
        }

    def _build_gpu_emit_payload(self, gpus: list[dict[str, Any]]) -> dict[str, Any]:
        """Flatten first GPU for backward compatibility; include full ``gpus`` list."""
        if not gpus:
            return self._empty_gpu_payload()
        g0 = gpus[0]
        return {
            "vendor": str(g0.get("vendor", "Unknown")),
            "model": str(g0.get("model", "Unknown")),
            "utilization": float(g0.get("utilization", 0.0)),
            "vram_used": float(g0.get("vram_used", 0.0)),
            "vram_total": float(g0.get("vram_total", 1.0)),
            "temperature_c": g0.get("temperature_c"),
            "fan_speed": g0.get("fan_speed"),
            "detected": True,
            "gpus": gpus,
            "gpu_count": len(gpus),
        }

    def _collect_gpu_data(self) -> dict[str, Any]:
        """Collect GPU metrics: prefer NVIDIA (multi-line CSV), else all AMD/Intel DRM devices."""
        nvidia = self._collect_nvidia_gpus()
        if nvidia:
            return self._build_gpu_emit_payload(nvidia)
        amd = self._collect_amd_gpus()
        if amd:
            return self._build_gpu_emit_payload(amd)
        intel = self._collect_intel_gpus()
        if intel:
            return self._build_gpu_emit_payload(intel)
        return self._empty_gpu_payload()

    def _collect_nvidia_gpus(self) -> list[dict[str, Any]]:
        """Collect metrics for all NVIDIA GPUs (one CSV row per device)."""
        gpus: list[dict[str, Any]] = []
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,fan.speed",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return gpus
            for raw_line in result.stdout.strip().splitlines():
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 6:
                        continue
                    gpus.append(
                        {
                            "vendor": "NVIDIA",
                            "model": parts[0],
                            "utilization": float(parts[1]),
                            "vram_used": float(parts[2]),
                            "vram_total": float(parts[3]) or 1.0,
                            "temperature_c": float(parts[4]),
                            "fan_speed": float(parts[5]),
                            "detected": True,
                        }
                    )
                except (ValueError, IndexError):
                    continue
        except (subprocess.SubprocessError, ValueError, IndexError, FileNotFoundError):
            pass
        return gpus

    def _collect_amd_gpus(self) -> list[dict[str, Any]]:
        """Collect AMD GPU metrics from sysfs (one entry per matching DRM device)."""
        gpus: list[dict[str, Any]] = []
        for device_path in self._get_drm_device_paths():
            vendor_path = os.path.join(device_path, "vendor")
            if not os.path.exists(vendor_path):
                continue
            with open(vendor_path) as f:
                vendor_id = f.read().strip()
            if vendor_id != "0x1002":
                continue
            gpus.append(
                {
                    "vendor": "AMD",
                    "model": self._read_gpu_model(device_path) or "AMD GPU",
                    "utilization": self._read_gpu_sysfs_value(device_path, "gpu_busy_percent")
                    or 0.0,
                    "vram_total": self._read_gpu_sysfs_value(
                        device_path, "mem_info_vram_total", scale=1 / 1024
                    )
                    or 1.0,
                    "vram_used": self._read_gpu_sysfs_value(
                        device_path, "mem_info_vram_used", scale=1 / 1024
                    )
                    or 0.0,
                    "temperature_c": self._read_gpu_hwmon_temperature(
                        device_path, prefixes=("amdgpu", "radeon")
                    ),
                    "fan_speed": self._read_gpu_hwmon_fan(device_path),
                    "detected": True,
                }
            )
        return gpus

    def _collect_intel_gpus(self) -> list[dict[str, Any]]:
        """Collect Intel GPU metrics from sysfs (one entry per matching DRM device)."""
        gpus: list[dict[str, Any]] = []
        for device_path in self._get_drm_device_paths():
            vendor_path = os.path.join(device_path, "vendor")
            if not os.path.exists(vendor_path):
                continue
            with open(vendor_path) as f:
                vendor_id = f.read().strip()
            if vendor_id != "0x8086":
                continue
            gpus.append(
                {
                    "vendor": "Intel",
                    "model": self._read_gpu_model(device_path) or "Intel GPU",
                    "utilization": self._read_gpu_sysfs_value(device_path, "gpu_busy_percent")
                    or 0.0,
                    "vram_total": self._read_gpu_sysfs_value(
                        device_path, "mem_info_vram_total", scale=1 / 1024
                    )
                    or 1.0,
                    "vram_used": self._read_gpu_sysfs_value(
                        device_path, "mem_info_vram_used", scale=1 / 1024
                    )
                    or 0.0,
                    "temperature_c": self._read_gpu_hwmon_temperature(
                        device_path, prefixes=("intel_gpu", "gpu")
                    ),
                    "fan_speed": self._read_gpu_hwmon_fan(device_path),
                    "detected": True,
                }
            )
        return gpus

    def _get_drm_device_paths(self) -> list[str]:
        """Return a list of direct GPU device sysfs paths under /sys/class/drm."""
        drm_path = "/sys/class/drm"
        paths: list[str] = []
        if not os.path.isdir(drm_path):
            return paths

        for entry in os.listdir(drm_path):
            if not entry.startswith("card") or entry.endswith("-DP"):
                continue

            device_path = os.path.join(drm_path, entry, "device")
            if os.path.isdir(device_path):
                paths.append(device_path)
        return paths

    def _read_gpu_model(self, device_path: str) -> str | None:
        """Attempt to read a GPU model string from sysfs."""
        product_name = self._read_gpu_sysfs_string(device_path, "product_name")
        if product_name:
            return product_name

        uevent_path = os.path.join(device_path, "uevent")
        if os.path.exists(uevent_path):
            try:
                with open(uevent_path) as f:
                    for line in f:
                        if line.startswith("PRODUCT="):
                            parts = line.strip().split("=")
                            if len(parts) == 2:
                                return parts[1]
            except Exception:
                pass

        return None

    def _read_gpu_sysfs_string(self, device_path: str, filename: str) -> str | None:
        """Read a string value from a sysfs GPU device node."""
        try:
            file_path = os.path.join(device_path, filename)
            if os.path.exists(file_path):
                with open(file_path) as f:
                    return f.read().strip()
        except Exception:
            pass
        return None

    def _read_gpu_sysfs_value(
        self,
        device_path: str,
        filename: str,
        scale: float = 1.0,
    ) -> float | None:
        """Read a numeric value from sysfs and optionally scale it."""
        try:
            file_path = os.path.join(device_path, filename)
            if not os.path.exists(file_path):
                return None
            with open(file_path) as f:
                raw = f.read().strip()
            if not raw:
                return None
            value = float(raw)
            return value * scale
        except (ValueError, OSError):
            return None

    def _read_gpu_hwmon_temperature(
        self,
        device_path: str,
        prefixes: tuple[str, ...],
    ) -> float | None:
        """Read GPU temperature from hwmon entries under the device path."""
        try:
            hwmon_root = os.path.join(device_path, "hwmon")
            if os.path.isdir(hwmon_root):
                for hwmon in os.listdir(hwmon_root):
                    hwmon_path = os.path.join(hwmon_root, hwmon)
                    if not os.path.isdir(hwmon_path):
                        continue
                    for entry in os.listdir(hwmon_path):
                        if entry.startswith("temp") and entry.endswith("_input"):
                            temp_value = self._read_gpu_sysfs_value(hwmon_path, entry)
                            if temp_value is not None and temp_value > 0:
                                return temp_value

            # Fallback to sensors labels
            return self._read_gpu_temp_from_sensors(prefixes=prefixes)
        except Exception:
            return None

    def _read_gpu_hwmon_fan(self, device_path: str) -> float | None:
        """Read GPU fan speed from hwmon entries, if available."""
        try:
            hwmon_root = os.path.join(device_path, "hwmon")
            if os.path.isdir(hwmon_root):
                for hwmon in os.listdir(hwmon_root):
                    hwmon_path = os.path.join(hwmon_root, hwmon)
                    if not os.path.isdir(hwmon_path):
                        continue
                    for entry in os.listdir(hwmon_path):
                        if entry.startswith("fan") and entry.endswith("_input"):
                            fan_value = self._read_gpu_sysfs_value(hwmon_path, entry)
                            if fan_value is not None and fan_value >= 0:
                                return fan_value
        except Exception:
            pass
        return None

    def _read_amd_gpu_temp(self) -> float | None:
        """Read AMD GPU temperature from sensors if available."""
        return self._read_gpu_temp_from_sensors(prefixes=("amdgpu", "radeon"))

    def _read_intel_gpu_temp(self) -> float | None:
        """Read Intel GPU temperature from sensors if available."""
        return self._read_gpu_temp_from_sensors(prefixes=("intel_gpu", "gpu"))

    def _read_gpu_temp_from_sensors(self, prefixes: tuple[str, ...]) -> float | None:
        """Try to read GPU temperature from sensors by label prefix."""
        try:
            temps = psutil.sensors_temperatures(fahrenheit=False)
            for key, entries in temps.items():
                for entry in entries:
                    label = entry.label.lower() if entry.label else key.lower()
                    if (
                        any(label.startswith(prefix) for prefix in prefixes)
                        and entry.current is not None
                        and entry.current > 0
                    ):
                        return float(entry.current)
        except Exception:
            pass
        return None

    @property
    def interval(self) -> float:
        return self._interval

    @interval.setter
    def interval(self, value: float) -> None:
        self._interval = max(0.1, value)
        log.debug("SystemMonitor interval updated to %fs", self._interval)

    @property
    def is_running(self) -> bool:
        """Return True if the monitor thread is active."""
        return self._thread is not None and self._thread.is_alive()
