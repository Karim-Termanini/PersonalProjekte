"""HypeDevHome — Package Manager Abstraction.

Abstract base class and implementations for different package managers.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from core.setup.package_progress import fraction_from_output_line

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Information about a package."""

    id: str
    name: str
    description: str
    version: str | None = None
    installed: bool = False
    size: str | None = None


class PackageManager(ABC):
    """Abstract base class for package managers."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor

    @abstractmethod
    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a package."""
        pass

    @abstractmethod
    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a package."""
        pass

    @abstractmethod
    async def is_installed(self, package_id: str) -> bool:
        """Check if a package is installed."""
        pass

    @abstractmethod
    async def search(self, query: str) -> list[PackageInfo]:
        """Search for packages."""
        pass

    @abstractmethod
    async def list_installed(self) -> list[PackageInfo]:
        """List installed packages."""
        pass

    @abstractmethod
    async def update_cache(self) -> bool:
        """Update package cache/repository."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the package manager."""
        pass

    @property
    @abstractmethod
    def requires_root(self) -> bool:
        """Whether this package manager requires root privileges."""
        pass

    async def _execute_with_progress(
        self,
        cmd: list[str],
        root: bool = False,
        progress_callback: Callable[[str, float], None] | None = None,
        progress_label: str = "Processing",
        timeout: float = 300.0,
    ) -> bool:
        """Execute a command with optional line-based % progress (from tool output)."""
        if progress_callback is None:
            result = await self._executor.run_async(cmd, root=root, timeout=timeout)
            if not result.success:
                log.warning(
                    "Command failed: %s (code=%d)\nstderr: %s",
                    " ".join(cmd),
                    result.returncode,
                    result.stderr[:500] if result.stderr else "",
                )
            return result.success

        last_frac = 0.0

        def on_line(line: str) -> None:
            nonlocal last_frac
            f = fraction_from_output_line(line)
            if f is not None:
                last_frac = max(last_frac, min(1.0, f))
            progress_callback(line[:200] if line else "", last_frac)

        progress_callback(f"{progress_label}…", 0.0)
        result = await self._executor.run_async_streaming(
            cmd, root=root, timeout=timeout, on_line=on_line
        )
        if result.success:
            progress_callback("Complete", 1.0)
        else:
            log.warning(
                "Command failed: %s (code=%d)\nstderr: %s",
                " ".join(cmd),
                result.returncode,
                result.stderr[:500] if result.stderr else "",
            )
            if last_frac < 1.0:
                progress_callback("Failed", last_frac)
        return result.success


class FlatpakManager(PackageManager):
    """Flatpak package manager."""

    @property
    def name(self) -> str:
        return "flatpak"

    @property
    def requires_root(self) -> bool:
        return False  # Flatpak uses user installation by default

    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a Flatpak package."""
        cmd = ["flatpak", "install", "--system", "-y", "--verbose", "flathub", package_id]
        return await self._execute_with_progress(
            cmd, progress_callback=progress_callback, progress_label=f"Installing {package_id}"
        )

    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a Flatpak package."""
        cmd = ["flatpak", "uninstall", "--system", "-y", "--verbose", package_id]
        return await self._execute_with_progress(
            cmd, progress_callback=progress_callback, progress_label=f"Removing {package_id}"
        )

    async def is_installed(self, package_id: str) -> bool:
        """Check if a Flatpak package is installed."""
        result = await self._executor.run_async(["flatpak", "info", package_id])
        return result.success

    async def search(self, query: str) -> list[PackageInfo]:
        """Search for Flatpak packages."""
        result = await self._executor.run_async(["flatpak", "search", query])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")
        for line in lines[1:]:  # Skip header
            if line.strip():
                parts = line.split("\t")
                if len(parts) >= 3:
                    package_id = parts[0].strip()
                    name = parts[1].strip()
                    description = parts[2].strip()
                    packages.append(PackageInfo(id=package_id, name=name, description=description))

        return packages

    async def list_installed(self) -> list[PackageInfo]:
        """List installed Flatpak packages."""
        result = await self._executor.run_async(
            ["flatpak", "list", "--columns=application,version,name"]
        )
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if line.strip():
                parts = line.split("\t")
                if len(parts) >= 3:
                    package_id = parts[0].strip()
                    version = parts[1].strip()
                    name = parts[2].strip()
                    packages.append(
                        PackageInfo(
                            id=package_id,
                            name=name,
                            description="",
                            version=version,
                            installed=True,
                        )
                    )

        return packages

    async def update_cache(self) -> bool:
        """Update Flatpak repository cache."""
        result = await self._executor.run_async(["flatpak", "update", "--appstream"])
        return result.success


class DnfManager(PackageManager):
    """DNF package manager (Fedora, RHEL, CentOS)."""

    @property
    def name(self) -> str:
        return "dnf"

    @property
    def requires_root(self) -> bool:
        return True

    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a package with DNF."""
        cmd = ["dnf", "install", "-y", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Installing {package_id}",
        )

    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a package with DNF."""
        cmd = ["dnf", "remove", "-y", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Removing {package_id}",
        )

    async def is_installed(self, package_id: str) -> bool:
        """Check if a package is installed with DNF."""
        result = await self._executor.run_async(["dnf", "list", "--installed", package_id])
        return result.success and "Installed Packages" in result.stdout

    async def search(self, query: str) -> list[PackageInfo]:
        """Search for packages with DNF."""
        result = await self._executor.run_async(["dnf", "search", query])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("===="):
                continue
            if line and not line.startswith(" ") and ":" in line:
                # Package name line
                name_part, desc_part = line.split(":", 1)
                package_name = name_part.strip()
                description = desc_part.strip()
                packages.append(
                    PackageInfo(id=package_name, name=package_name, description=description)
                )

        return packages

    async def list_installed(self) -> list[PackageInfo]:
        """List installed packages with DNF."""
        result = await self._executor.run_async(["dnf", "list", "--installed"])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")
        in_installed_section = False

        for line in lines:
            if "Installed Packages" in line:
                in_installed_section = True
                continue
            if not in_installed_section:
                continue

            if line.strip() and not line.startswith(" "):
                parts = line.split()
                if parts:
                    package_name = parts[0].split(".")[0]  # Remove .arch suffix
                    version = parts[1] if len(parts) > 1 else None
                    packages.append(
                        PackageInfo(
                            id=package_name,
                            name=package_name,
                            description="",
                            version=version,
                            installed=True,
                        )
                    )

        return packages

    async def update_cache(self) -> bool:
        """Update DNF repository cache."""
        result = await self._executor.run_async(["dnf", "makecache"], root=True)
        return result.success


class AptManager(PackageManager):
    """APT package manager (Debian, Ubuntu)."""

    @property
    def name(self) -> str:
        return "apt"

    @property
    def requires_root(self) -> bool:
        return True

    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a package with APT."""
        cmd = ["apt", "install", "-y", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Installing {package_id}",
        )

    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a package with APT."""
        cmd = ["apt", "remove", "-y", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Removing {package_id}",
        )

    async def is_installed(self, package_id: str) -> bool:
        """Check if a package is installed with APT."""
        result = await self._executor.run_async(["dpkg", "-l", package_id])
        return result.success and "ii" in result.stdout

    async def search(self, query: str) -> list[PackageInfo]:
        """Search for packages with APT."""
        result = await self._executor.run_async(["apt", "search", query])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if "/" in line:
                parts = line.split("/", 1)
                if len(parts) >= 2:
                    package_name = parts[0].strip()
                    description = (
                        parts[1].split("-", 1)[-1].strip() if "-" in parts[1] else parts[1].strip()
                    )
                    packages.append(
                        PackageInfo(id=package_name, name=package_name, description=description)
                    )

        return packages

    async def list_installed(self) -> list[PackageInfo]:
        """List installed packages with APT."""
        result = await self._executor.run_async(["dpkg", "--get-selections"])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if line and "\t" in line:
                package_name, status = line.split("\t", 1)
                if status.strip() == "install":
                    packages.append(
                        PackageInfo(
                            id=package_name, name=package_name, description="", installed=True
                        )
                    )

        return packages

    async def update_cache(self) -> bool:
        """Update APT repository cache."""
        result = await self._executor.run_async(["apt", "update"], root=True)
        return result.success


class PacmanManager(PackageManager):
    """Pacman package manager (Arch Linux)."""

    @property
    def name(self) -> str:
        return "pacman"

    @property
    def requires_root(self) -> bool:
        return True

    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a package with Pacman."""
        cmd = ["pacman", "-S", "--noconfirm", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Installing {package_id}",
        )

    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a package with Pacman."""
        cmd = ["pacman", "-R", "--noconfirm", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Removing {package_id}",
        )

    async def is_installed(self, package_id: str) -> bool:
        """Check if a package is installed with Pacman."""
        result = await self._executor.run_async(["pacman", "-Q", package_id])
        return result.success

    async def search(self, query: str) -> list[PackageInfo]:
        """Search for packages with Pacman."""
        result = await self._executor.run_async(["pacman", "-Ss", query])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")

        for line in lines:
            if (
                line.startswith("core/")
                or line.startswith("extra/")
                or line.startswith("community/")
            ):
                # Package name line
                parts = line.split()
                if parts:
                    repo_package = parts[0]
                    package_name = repo_package.split("/")[-1]
                    description = " ".join(parts[1:]) if len(parts) > 1 else ""
                    packages.append(
                        PackageInfo(id=package_name, name=package_name, description=description)
                    )

        return packages

    async def list_installed(self) -> list[PackageInfo]:
        """List installed packages with Pacman."""
        result = await self._executor.run_async(["pacman", "-Q"])
        if not result.success:
            return []

        packages = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if line:
                parts = line.split()
                if len(parts) >= 2:
                    package_name = parts[0]
                    version = parts[1]
                    packages.append(
                        PackageInfo(
                            id=package_name,
                            name=package_name,
                            description="",
                            version=version,
                            installed=True,
                        )
                    )

        return packages

    async def update_cache(self) -> bool:
        """Update Pacman repository cache."""
        result = await self._executor.run_async(["pacman", "-Sy"], root=True)
        return result.success


class ZypperManager(PackageManager):
    """Zypper package manager (openSUSE, SUSE)."""

    @property
    def name(self) -> str:
        return "zypper"

    @property
    def requires_root(self) -> bool:
        return True

    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a package with Zypper."""
        cmd = ["zypper", "--non-interactive", "install", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Installing {package_id}",
        )

    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a package with Zypper."""
        cmd = ["zypper", "--non-interactive", "remove", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Removing {package_id}",
        )

    async def is_installed(self, package_id: str) -> bool:
        """Check if a package is installed with Zypper."""
        result = await self._executor.run_async(["rpm", "-q", package_id])
        return result.success

    async def search(self, query: str) -> list[PackageInfo]:
        """Search for packages with Zypper."""
        result = await self._executor.run_async(["zypper", "search", query])
        if not result.success:
            return []

        packages: list[PackageInfo] = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("--") or "|" not in line:
                continue
            parts = [part.strip() for part in line.split("|")]
            if len(parts) < 4:
                continue
            status = parts[0].lower()
            package_name = parts[2]
            description = parts[3]
            if status in {"i", "v"} or package_name:
                packages.append(
                    PackageInfo(id=package_name, name=package_name, description=description)
                )
        return packages

    async def list_installed(self) -> list[PackageInfo]:
        """List installed packages with Zypper."""
        result = await self._executor.run_async(["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}\n"])
        if not result.success:
            return []

        packages: list[PackageInfo] = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                package_name = parts[0].strip()
                version = parts[1].strip()
                packages.append(
                    PackageInfo(
                        id=package_name,
                        name=package_name,
                        description="",
                        version=version,
                        installed=True,
                    )
                )
        return packages

    async def update_cache(self) -> bool:
        """Refresh Zypper repositories."""
        result = await self._executor.run_async(["zypper", "--non-interactive", "refresh"], root=True)
        return result.success


class ApkManager(PackageManager):
    """APK package manager (Alpine Linux)."""

    @property
    def name(self) -> str:
        return "apk"

    @property
    def requires_root(self) -> bool:
        return True

    async def install(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Install a package with APK."""
        cmd = ["apk", "add", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Installing {package_id}",
        )

    async def remove(
        self, package_id: str, progress_callback: Callable[[str, float], None] | None = None
    ) -> bool:
        """Remove a package with APK."""
        cmd = ["apk", "del", package_id]
        return await self._execute_with_progress(
            cmd,
            root=True,
            progress_callback=progress_callback,
            progress_label=f"Removing {package_id}",
        )

    async def is_installed(self, package_id: str) -> bool:
        """Check if a package is installed with APK."""
        result = await self._executor.run_async(["apk", "info", "-e", package_id])
        return result.success

    async def search(self, query: str) -> list[PackageInfo]:
        """Search for packages with APK."""
        result = await self._executor.run_async(["apk", "search", query])
        if not result.success:
            return []

        packages: list[PackageInfo] = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            package_name = line
            if "-" in line:
                package_name = line.rsplit("-", 2)[0]
            packages.append(PackageInfo(id=package_name, name=package_name, description=""))
        return packages

    async def list_installed(self) -> list[PackageInfo]:
        """List installed packages with APK."""
        result = await self._executor.run_async(["apk", "info", "-v"])
        if not result.success:
            return []

        packages: list[PackageInfo] = []
        lines = result.stdout.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            package_name = line
            version = None
            if "-" in line:
                parts = line.rsplit("-", 2)
                if len(parts) >= 3:
                    package_name = parts[0]
                    version = f"{parts[1]}-{parts[2]}"
            packages.append(
                PackageInfo(
                    id=package_name,
                    name=package_name,
                    description="",
                    version=version,
                    installed=True,
                )
            )
        return packages

    async def update_cache(self) -> bool:
        """Update APK package index."""
        result = await self._executor.run_async(["apk", "update"], root=True)
        return result.success


class PackageManagerFactory:
    """Factory for creating package manager instances."""

    @staticmethod
    def create(manager_name: str, executor: HostExecutor) -> PackageManager:
        """Create a package manager instance."""
        managers = {
            "flatpak": FlatpakManager,
            "dnf": DnfManager,
            "apt": AptManager,
            "pacman": PacmanManager,
            "zypper": ZypperManager,
            "apk": ApkManager,
        }

        manager_class = cast(type[PackageManager], managers.get(manager_name.lower()))
        if not manager_class:
            raise ValueError(f"Unsupported package manager: {manager_name}")

        return manager_class(executor)
