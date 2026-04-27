"""HypeDevHome — Distribution Detection Service.

Detects the host Linux distribution and available package managers.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class DistroInfo:
    """Information about the detected Linux distribution."""

    distro: str
    version: str
    package_manager: str
    has_flatpak: bool
    has_snap: bool
    id_like: list[str]
    pretty_name: str
    is_flatpak: bool = False

    def __str__(self) -> str:
        return f"{self.pretty_name} ({self.distro} {self.version})"


class DistroDetector:
    """Detects Linux distribution and available package managers."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor
        self._cached_info: DistroInfo | None = None

    async def detect(self) -> DistroInfo:
        """Detect distribution information."""
        if self._cached_info:
            return self._cached_info

        # Check if we're running in Flatpak
        is_flatpak = os.path.exists("/.flatpak-info")

        # Read /etc/os-release
        os_release = await self._read_os_release()
        distro = os_release.get("ID", "unknown").lower()
        version = os_release.get("VERSION_ID", "unknown")
        id_like = os_release.get("ID_LIKE", "").lower().split()
        pretty_name = os_release.get("PRETTY_NAME", f"{distro} {version}")

        # Detect package manager
        package_manager = await self._detect_package_manager(distro, id_like)

        # Check for Flatpak and Snap
        has_flatpak = await self._check_command_exists("flatpak")
        has_snap = await self._check_command_exists("snap")

        info = DistroInfo(
            distro=distro,
            version=version,
            package_manager=package_manager,
            has_flatpak=has_flatpak,
            has_snap=has_snap,
            id_like=id_like,
            pretty_name=pretty_name,
            is_flatpak=is_flatpak,
        )

        self._cached_info = info
        log.info("Detected distribution: %s", info)
        return info

    async def _read_os_release(self) -> dict[str, str]:
        """Read and parse /etc/os-release file."""
        result = await self._executor.run_async(["cat", "/etc/os-release"])
        if not result.success:
            log.warning("Failed to read /etc/os-release, using defaults")
            return {}

        os_release = {}
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and "=" in line:
                key, value = line.split("=", 1)
                # Remove quotes from value
                value = value.strip("\"'")
                os_release[key] = value

        return os_release

    async def _detect_package_manager(self, distro: str, id_like: list[str]) -> str:
        """Detect the primary package manager for the distribution."""
        # Check for specific package managers
        package_managers = [
            ("apt", ["debian", "ubuntu", "linuxmint"]),
            ("dnf", ["fedora", "rhel", "centos"]),
            ("yum", ["rhel", "centos", "amazon"]),
            ("pacman", ["arch", "manjaro", "endeavouros"]),
            ("zypper", ["opensuse", "suse"]),
            ("apk", ["alpine"]),
            ("emerge", ["gentoo"]),
        ]

        # Check current distro first
        for pm, distros in package_managers:
            if distro in distros and await self._check_command_exists(pm):
                return pm

        # Check ID_LIKE distros
        for like in id_like:
            for pm, distros in package_managers:
                if like in distros and await self._check_command_exists(pm):
                    return pm

        # Fallback: check for any known package manager
        for pm, _ in package_managers:
            if await self._check_command_exists(pm):
                return pm

        log.warning("No known package manager detected")
        return "unknown"

    async def _check_command_exists(self, command: str) -> bool:
        """Check if a command exists on the system."""
        result = await self._executor.run_async(["which", command])
        return result.success

    async def get_supported_package_managers(self) -> list[str]:
        """Get list of all supported package managers available on the system."""
        info = await self.detect()
        managers = []

        # Primary package manager
        if info.package_manager != "unknown":
            managers.append(info.package_manager)

        # Flatpak
        if info.has_flatpak:
            managers.append("flatpak")

        # Snap (optional)
        if info.has_snap:
            managers.append("snap")

        return managers

    async def is_supported_distro(self) -> bool:
        """Check if the distribution is supported by HypeDevHome."""
        info = await self.detect()
        supported_distros = [
            "fedora",
            "ubuntu",
            "debian",
            "arch",
            "manjaro",
            "linuxmint",
            "opensuse",
            "rhel",
            "centos",
        ]

        # Check direct match
        if info.distro in supported_distros:
            return True

        # Check ID_LIKE
        return any(like in supported_distros for like in info.id_like)
