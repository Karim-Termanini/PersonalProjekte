"""HypeDevHome — Package Installer.

Uses the PackageManager abstraction for installation.
"""

from __future__ import annotations

import configparser
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from core.setup.distro_detector import DistroDetector
from core.setup.models import AppInfo, SetupStatus
from core.setup.package_catalog import PackageCatalog
from core.setup.package_manager import PackageManagerFactory

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor
    from core.setup.package_manager import PackageInfo, PackageManager

log = logging.getLogger(__name__)


class PackageInstaller:
    """Manages application installation using PackageManager abstraction."""

    def __init__(self, executor: HostExecutor, *, native_host_access: bool = True) -> None:
        self._executor = executor
        self._distro_detector = DistroDetector(executor)
        self._package_catalog = PackageCatalog()
        self._package_managers: dict[str, PackageManager] = {}
        self._initialized = False
        # Native apt/dnf/pacman/zypper/apk operations require host access.
        # In Flatpak sandbox, we keep visibility but block native removal when OFF.
        self._native_host_access_enabled = native_host_access

    def set_native_host_access_enabled(self, enabled: bool) -> None:
        self._native_host_access_enabled = bool(enabled)

    async def initialize(self) -> bool:
        """Initialize the installer with detected package managers."""
        if self._initialized:
            return True

        try:
            # Load package catalog
            if not await self._package_catalog.load():
                log.warning("Failed to load package catalog")

            # Detect distribution
            distro_info = await self._distro_detector.detect()
            log.info("Detected distribution: %s", distro_info)

            # Get supported package managers
            supported_managers = await self._distro_detector.get_supported_package_managers()

            # Create package manager instances
            for manager_name in supported_managers:
                try:
                    manager = PackageManagerFactory.create(manager_name, self._executor)
                    self._package_managers[manager_name] = manager
                    log.info("Created package manager: %s", manager_name)
                except ValueError as e:
                    log.warning("Skipping unsupported package manager %s: %s", manager_name, e)

            self._initialized = True
            return True

        except Exception as e:
            log.error("Error initializing package installer: %s", e)
            return False

    async def install_app(self, app: AppInfo, progress_callback=None) -> bool:
        """Install a single application."""
        app.status = SetupStatus.RUNNING

        try:
            # Determine which package manager to use
            package_manager = await self._select_package_manager(app)
            if not package_manager:
                log.error("No suitable package manager found for %s", app.name)
                app.status = SetupStatus.FAILED
                return False

            log.info("Installing %s via %s...", app.name, package_manager.name)

            # Install the package
            success = await package_manager.install(
                app.package_name,
                progress_callback=progress_callback,
            )

            if success:
                app.status = SetupStatus.COMPLETED
                log.info("Successfully installed %s", app.name)
            else:
                app.status = SetupStatus.FAILED
                log.error("Failed to install %s", app.name)

            return success

        except Exception as e:
            log.exception("Error installing %s: %s", app.name, e)
            app.status = SetupStatus.FAILED
            return False

    async def _select_package_manager(self, app: AppInfo) -> PackageManager | None:
        """Select the best package manager for an application."""
        # Prefer Flatpak if available and app has Flatpak ID
        if app.flatpak_id and not app.force_system_pkg and "flatpak" in self._package_managers:
            return self._package_managers["flatpak"]

        # Get distribution info to select appropriate system package manager
        distro_info = await self._distro_detector.detect()

        # Map distribution to package manager
        distro_to_manager = {
            "ubuntu": "apt",
            "debian": "apt",
            "linuxmint": "apt",
            "fedora": "dnf",
            "rhel": "dnf",
            "centos": "dnf",
            "arch": "pacman",
            "manjaro": "pacman",
            "opensuse": "zypper",
            "suse": "zypper",
        }

        # Try the distribution's primary package manager
        manager_name = distro_to_manager.get(distro_info.distro)
        if manager_name and manager_name in self._package_managers:
            return self._package_managers[manager_name]

        # Try any available system package manager
        for manager_name in ["apt", "dnf", "pacman", "zypper", "apk"]:
            if manager_name in self._package_managers:
                return self._package_managers[manager_name]

        # Fallback to Flatpak if nothing else
        if "flatpak" in self._package_managers:
            return self._package_managers["flatpak"]

        return None

    async def is_installed(self, app: AppInfo) -> bool:
        """Check if an application is already installed."""
        # Try Flatpak first
        if app.flatpak_id and "flatpak" in self._package_managers:
            flatpak_manager = self._package_managers["flatpak"]
            if await flatpak_manager.is_installed(app.flatpak_id):
                return True

        # Try system package managers
        for manager_name, manager in self._package_managers.items():
            if manager_name != "flatpak" and await manager.is_installed(app.package_name):
                return True

        return False

    async def get_app_from_catalog(self, package_id: str) -> AppInfo | None:
        """Get AppInfo for a package from the catalog."""
        distro_info = await self._distro_detector.detect()
        return self._package_catalog.get_package_for_distro(package_id, distro_info)

    async def get_available_packages(self) -> list[AppInfo]:
        """Get all available packages as AppInfo objects."""
        distro_info = await self._distro_detector.detect()
        packages = self._package_catalog.get_all_packages()

        app_infos = []
        for package in packages:
            app_info = self._package_catalog.get_package_for_distro(package.id, distro_info)
            if app_info:
                # Check if installed
                app_info.selected = False
                app_info.status = SetupStatus.PENDING
                app_infos.append(app_info)

        return app_infos

    async def get_installed_packages(
        self,
        *,
        include_container_apps: bool = False,
        max_container_apps_per_env: int = 40,
    ) -> list[AppInfo]:
        """Get installed packages from all detected package managers.

        Args:
            include_container_apps: Include read-only “container executables” discovered
                inside distrobox/toolbox environments (Phase 3).
            max_container_apps_per_env: Upper bound per container to keep UI responsive.
        """
        if not self._initialized and not await self.initialize():
            return []

        installed_apps: list[AppInfo] = []
        seen_ids: set[str] = set()
        seen_names: set[str] = set()

        for manager_name, manager in self._package_managers.items():
            try:
                packages = await manager.list_installed()
            except Exception:
                log.exception("Failed listing installed packages for manager %s", manager_name)
                continue

            for package in packages:
                package_id = package.id.strip()
                if not package_id:
                    continue

                norm_id = (
                    package_id.lower()
                    if manager_name in ("dnf", "apt", "zypper")
                    else package_id
                )
                unique_id = f"{manager_name}:{norm_id}"
                if unique_id in seen_ids:
                    continue
                seen_ids.add(unique_id)

                display_name = package.name.strip() if package.name.strip() else package_id
                description = package.description.strip() if package.description.strip() else (
                    f"Installed via {manager_name}"
                )
                pkg_for_remove = (
                    norm_id if manager_name in ("dnf", "apt", "zypper") else package_id
                )
                app = AppInfo(
                    id=unique_id,
                    name=display_name,
                    description=description,
                    icon="application-x-executable-symbolic",
                    package_name=pkg_for_remove,
                    category=manager_name,
                    ui_category="flatpak" if manager_name == "flatpak" else "all apps",
                )
                app.selected = False
                app.status = SetupStatus.COMPLETED
                installed_apps.append(app)
                seen_names.add(display_name.strip().lower())

        for desktop_app in self._discover_desktop_apps(seen_names):
            dp = desktop_app.desktop_path
            if dp and desktop_app.category in ("dnf", "zypper"):
                resolved = await self._resolve_rpm_package_for_desktop(Path(dp))
                if resolved:
                    desktop_app.package_name = resolved.lower()
                    desktop_app.id = f"{desktop_app.category}:{desktop_app.package_name}"
            elif dp and desktop_app.category == "apt":
                resolved = await self._resolve_deb_package_for_desktop(Path(dp))
                if resolved:
                    desktop_app.package_name = resolved.lower()
                    desktop_app.id = f"{desktop_app.category}:{desktop_app.package_name}"

            if desktop_app.id in seen_ids:
                continue
            seen_ids.add(desktop_app.id)
            installed_apps.append(desktop_app)

        if include_container_apps:
            try:
                container_apps = await self._discover_container_apps(
                    max_per_env=max_container_apps_per_env,
                )
                installed_apps.extend(container_apps)
            except Exception:
                # Container listing must never break host app discovery.
                log.exception("Failed to discover container apps")

        installed_apps.sort(key=lambda app: app.name.lower())
        return installed_apps

    async def _discover_container_apps(
        self,
        *,
        max_per_env: int,
    ) -> list[AppInfo]:
        """Discover executable names inside running dev containers (read-only)."""
        # Import locally to keep PackageInstaller independent of UI/container deps at import time.
        from core.setup.environments import EnvironmentManager

        env = EnvironmentManager(self._executor)
        await env.initialize()
        envs = await env.list_environments()
        if not envs:
            return []

        apps: list[AppInfo] = []
        seen: set[str] = set()

        # Only list containers that look “started”.
        def _is_env_running(status: str) -> bool:
            s = (status or "").strip().lower()
            return s.startswith(("up", "running", "active")) or "running" in s or s == "on"

        for e in envs:
            name = (e.get("name") or "").strip()
            engine = (e.get("engine") or "distrobox").strip().lower()
            status = e.get("status") or ""
            if not name or not _is_env_running(status):
                continue

            # List a small sample of executables from common bin dirs.
            inner = (
                "for d in /usr/bin /bin; do "
                "[ -d \"$d\" ] && ls -1 \"$d\" 2>/dev/null; "
                "done | head -"
                f"{max_per_env}"
            )

            if engine == "toolbox":
                cmd = ["toolbox", "enter", name, "--", "sh", "-c", inner]
            else:
                cmd = ["distrobox", "enter", name, "--", "sh", "-c", inner]

            res = await self._executor.run_async(cmd, timeout=30)
            if not res.success or not res.stdout.strip():
                continue

            for line in res.stdout.splitlines():
                bin_name = line.strip()
                if not bin_name:
                    continue
                if "/" in bin_name or " " in bin_name:
                    continue
                # id encodes engine/name to avoid collisions.
                app_id = f"container:{engine}:{name}:{bin_name}"
                if app_id in seen:
                    continue
                seen.add(app_id)

                apps.append(
                    AppInfo(
                        id=app_id,
                        name=bin_name,
                        description=f"Executable inside {name}",
                        icon="application-x-executable-symbolic",
                        package_name=name,
                        category="container",
                        ui_category="container",
                        selected=False,
                        status=SetupStatus.COMPLETED,
                    )
                )

        return apps

    async def _resolve_rpm_package_for_desktop(self, desktop_path: Path) -> str | None:
        """Owning RPM name for a .desktop file (fixes reverse-DNS stem vs rpm name)."""
        try:
            res = await self._executor.run_async(
                ["rpm", "-qf", str(desktop_path), "--qf", "%{NAME}\\n"],
                timeout=15,
            )
            if not res.success or not res.stdout.strip():
                return None
            return res.stdout.strip().splitlines()[0].strip()
        except Exception:
            log.debug("rpm -qf failed for %s", desktop_path)
            return None

    async def _resolve_deb_package_for_desktop(self, desktop_path: Path) -> str | None:
        """Owning Debian package for a .desktop path."""
        try:
            res = await self._executor.run_async(
                ["dpkg-query", "-S", str(desktop_path)],
                timeout=15,
            )
            if not res.success or not res.stdout.strip():
                return None
            line = res.stdout.strip().splitlines()[0]
            return line.split(":")[0].strip()
        except Exception:
            log.debug("dpkg-query -S failed for %s", desktop_path)
            return None

    async def remove_installed_app(
        self,
        app: AppInfo,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Remove installed app by detected source/category."""
        if not self._initialized and not await self.initialize():
            return False

        source = (app.category or "").strip().lower()
        if source in {"manual", "system"}:
            log.info("Skipping uninstall for manual/system app: %s", app.name)
            return False

        # Phase 2: enforce sandbox-friendly boundary.
        # If running inside Flatpak and Host Access is OFF, block native removals
        # (apt/dnf/pacman/zypper/apk). Flatpak removals remain allowed.
        if (
            self._executor.is_flatpak
            and not self._native_host_access_enabled
            and source != "flatpak"
        ):
            log.warning(
                "Blocking native uninstall in Flatpak sandbox (Host Access OFF): source=%s app=%s",
                source,
                app.name,
            )
            return False

        manager = self._package_managers.get(source)
        if manager is None:
            log.warning("No package manager for source %s (app=%s)", source, app.name)
            return False

        package_id = app.flatpak_id if source == "flatpak" and app.flatpak_id else app.package_name
        if not package_id:
            log.warning("No package id for uninstall: %s", app.name)
            return False
        return await manager.remove(package_id, progress_callback=progress_callback)

    async def search_packages(self, query: str, source: str) -> list[PackageInfo]:
        """Search packages in selected source/package manager."""
        if not self._initialized and not await self.initialize():
            return []
        source_key = source.strip().lower()
        manager = self._package_managers.get(source_key)
        if manager is None:
            return []
        try:
            return await manager.search(query)
        except Exception:
            log.exception("Search failed for source %s query=%s", source_key, query)
            return []

    async def install_package_by_source(
        self,
        package_id: str,
        source: str,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Install one package from specific source."""
        if not self._initialized and not await self.initialize():
            return False
        source_key = source.strip().lower()
        manager = self._package_managers.get(source_key)
        if manager is None:
            return False
        try:
            return await manager.install(package_id, progress_callback=progress_callback)
        except Exception:
            log.exception("Install failed for source %s package=%s", source_key, package_id)
            return False


    async def get_full_package_description(self, source: str, package_id: str) -> str:
        """Get detailed package description text for tooltip/details UI."""
        source_key = source.strip().lower()
        pkg = package_id.strip()
        if not pkg:
            return ""

        try:
            if source_key == "dnf":
                res = await self._executor.run_async(
                    ["dnf", "repoquery", "--info", pkg], timeout=15
                )
                if not res.success:
                    log.debug("dnf repoquery failed for %s: %s", pkg, res.stderr)
                    return ""
                lines = res.stdout.splitlines()
                out: list[str] = []
                in_desc = False
                for line in lines:
                    if line.startswith("Description"):
                        in_desc = True
                        part = line.split(":", 1)[1].strip() if ":" in line else ""
                        if part:
                            out.append(part)
                        continue
                    if in_desc:
                        stripped = line.strip()
                        if stripped == "":
                            if out:
                                break
                            continue
                        if stripped.startswith(":"):
                            stripped = stripped[1:].strip()
                        if not line.startswith(" ") and not line.startswith("\t"):
                            break
                        if stripped:
                            out.append(stripped)
                return " ".join([x for x in out if x]).strip()

            if source_key == "apt":
                res = await self._executor.run_async(["apt-cache", "show", pkg], timeout=20)
                if not res.success:
                    return ""
                out: list[str] = []
                in_desc = False
                for line in res.stdout.splitlines():
                    if line.startswith("Description:"):
                        in_desc = True
                        out.append(line.split(":", 1)[1].strip())
                        continue
                    if in_desc:
                        if line.startswith(" "):
                            out.append(line.strip())
                        else:
                            break
                return "\n".join([x for x in out if x]).strip()

            if source_key == "pacman":
                res = await self._executor.run_async(["pacman", "-Si", pkg], timeout=20)
                if not res.success:
                    return ""
                for line in res.stdout.splitlines():
                    if line.lower().startswith("description"):
                        return line.split(":", 1)[1].strip() if ":" in line else ""
                return ""

            if source_key == "zypper":
                res = await self._executor.run_async(["zypper", "info", pkg], timeout=20)
                if not res.success:
                    return ""
                for line in res.stdout.splitlines():
                    if line.lower().startswith("description"):
                        return line.split(":", 1)[1].strip() if ":" in line else ""
                return ""

            if source_key == "apk":
                res = await self._executor.run_async(["apk", "info", "-d", pkg], timeout=20)
                if not res.success:
                    return ""
                lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
                return "\n".join(lines[1:]).strip() if len(lines) > 1 else (lines[0] if lines else "")

            if source_key == "flatpak":
                import json
                import re as re_mod
                import urllib.request
                try:
                    url = f"https://flathub.org/api/v2/appstream/{pkg}"
                    with urllib.request.urlopen(url, timeout=15) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                    desc_html = data.get("description", "")
                    if desc_html:
                        text = re_mod.sub(r"<[^>]+>", " ", desc_html)
                        text = re_mod.sub(r"\s+", " ", text).strip()
                        return text
                except Exception:
                    pass
                for cmd in (
                    ["flatpak", "remote-info", "--system", "flathub", pkg],
                    ["flatpak", "remote-info", "flathub", pkg],
                ):
                    res = await self._executor.run_async(cmd, timeout=30)
                    if not res.success:
                        continue
                    lines = [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]
                    if not lines:
                        continue
                    first_line = lines[0]
                    if " - " in first_line:
                        return first_line.split(" - ", 1)[1].strip()
                    return first_line
                return ""

        except Exception:
            log.exception("get_full_package_description failed for %s:%s", source_key, pkg)

        return ""

    async def list_packages_by_source(
        self, source: str, limit: int = 600
    ) -> list[tuple[str, str, str]]:
        """List available package ids/names/descriptions for source (picker preload)."""
        source_key = source.strip().lower()
        limit = max(1, min(limit, 5000))
        if source_key == "pacman":
            result = await self._executor.run_async(["pacman", "-Slq"])
            if not result.success:
                return []
            names = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return [(n, n, "") for n in names[:limit]]
        if source_key == "apt":
            result = await self._executor.run_async(["apt-cache", "pkgnames"])
            if not result.success:
                return []
            names = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return [(n, n, "") for n in names[:limit]]
        if source_key == "dnf":
            result = await self._executor.run_async(
                ["dnf", "search", "", "--quiet"], timeout=30
            )
            if not result.success:
                return []
            out_dnf: list[tuple[str, str, str]] = []
            for line in result.stdout.splitlines():
                s = line.strip()
                if not s or s.startswith("Matched") or s.startswith("="):
                    continue
                parts = s.split(None, 1)
                if parts:
                    pkg_name = parts[0].split(".")[0]
                    desc = parts[1] if len(parts) > 1 else ""
                    out_dnf.append((pkg_name, pkg_name, desc))
                if len(out_dnf) >= limit:
                    break
            return out_dnf
        if source_key == "zypper":
            result = await self._executor.run_async(["zypper", "search", "-t", "package"])
            if not result.success:
                return []
            out: list[tuple[str, str, str]] = []
            for line in result.stdout.splitlines():
                s = line.strip()
                if not s or "|" not in s or s.startswith("--"):
                    continue
                parts = [p.strip() for p in s.split("|")]
                if len(parts) < 4:
                    continue
                pkg_id = parts[2]
                if pkg_id:
                    out.append((pkg_id, pkg_id, parts[3] if len(parts) > 3 else ""))
                if len(out) >= limit:
                    break
            return out
        if source_key == "apk":
            result = await self._executor.run_async(["apk", "search"])
            if not result.success:
                return []
            names = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return [(n, n, "") for n in names[:limit]]
        if source_key == "flatpak":
            for flag in ["--system", ""]:
                cmd = ["flatpak", "remote-ls", "--app", "--columns=application,name,description"]
                if flag:
                    cmd.append(flag)
                cmd.append("flathub")
                result = await self._executor.run_async(cmd, timeout=30)
                if result.success and result.stdout.strip():
                    out_fp: list[tuple[str, str, str]] = []
                    for line in result.stdout.splitlines():
                        s = line.strip()
                        if not s:
                            continue
                        parts = s.split("\t")
                        pkg_id = parts[0].strip()
                        pkg_name = parts[1].strip() if len(parts) > 1 and parts[1].strip() else pkg_id
                        pkg_desc = parts[2].strip() if len(parts) > 2 else ""
                        out_fp.append((pkg_id, pkg_name, pkg_desc))
                        if len(out_fp) >= limit:
                            break
                    return out_fp
            return []
        return []

    def _discover_desktop_apps(self, seen_names: set[str]) -> list[AppInfo]:
        """Discover desktop-launchable apps (including manual/internet installs)."""
        desktop_dirs = [
            Path.home() / ".local/share/applications",
            Path("/usr/local/share/applications"),
            Path("/usr/share/applications"),
            Path("/var/lib/flatpak/exports/share/applications"),
        ]

        apps: list[AppInfo] = []
        seen_desktop_ids: set[str] = set()
        for desktop_dir in desktop_dirs:
            if not desktop_dir.exists():
                continue
            for file_path in desktop_dir.glob("*.desktop"):
                app = self._parse_desktop_entry(file_path)
                if app is None:
                    continue
                key = app.id.strip().lower()
                name_key = app.name.strip().lower()
                if key in seen_desktop_ids or name_key in seen_names:
                    continue
                seen_desktop_ids.add(key)
                seen_names.add(name_key)
                apps.append(app)
        return apps

    def _parse_desktop_entry(self, file_path: Path) -> AppInfo | None:
        """Parse a .desktop file into an AppInfo row."""
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(file_path, encoding="utf-8")
        except Exception:
            log.debug("Skipping unreadable desktop entry: %s", file_path)
            return None

        if "Desktop Entry" not in parser:
            return None
        entry = parser["Desktop Entry"]
        if entry.get("Type", "").strip().lower() != "application":
            return None
        if entry.get("NoDisplay", "").strip().lower() == "true":
            return None
        if entry.get("Hidden", "").strip().lower() == "true":
            return None

        name = entry.get("Name", "").strip()
        exec_cmd = entry.get("Exec", "").strip()
        if not name:
            return None

        source = self._detect_desktop_source(file_path, exec_cmd, entry)
        desktop_categories = entry.get("Categories", "")
        app_id = f"{source}:{file_path.stem}"
        description = entry.get("Comment", "").strip() or f"Desktop app ({source})"
        icon = entry.get("Icon", "").strip() or "application-x-executable-symbolic"
        app = AppInfo(
            id=app_id,
            name=name,
            description=description,
            icon=icon,
            package_name=file_path.stem,
            desktop_path=str(file_path),
            category=source,
            ui_category=self._map_ui_category(source, desktop_categories),
        )
        app.selected = False
        app.status = SetupStatus.COMPLETED
        return app

    def _detect_desktop_source(
        self, file_path: Path, exec_cmd: str, entry: configparser.SectionProxy
    ) -> str:
        """Infer where an app came from for display labeling."""
        low_exec = exec_cmd.lower()
        low_path = str(file_path).lower()
        if "flatpak" in low_exec or "x-flatpak" in entry or "/flatpak/" in low_path:
            return "flatpak"
        if low_path.startswith(str((Path.home() / ".local/share/applications")).lower()):
            return "manual"
        if "/opt/" in low_exec or low_exec.startswith(str(Path.home()).lower()):
            return "manual"
        if os.path.exists("/etc/debian_version"):
            return "apt"
        if os.path.exists("/etc/fedora-release"):
            return "dnf"
        if os.path.exists("/etc/arch-release"):
            return "pacman"
        if os.path.exists("/etc/alpine-release"):
            return "apk"
        if os.path.exists("/etc/SuSE-release") or os.path.exists("/etc/zypp"):
            return "zypper"
        return "system"

    def _map_ui_category(self, source: str, desktop_categories: str) -> str:
        """Map desktop/source data to fixed UI categories."""
        source_key = source.strip().lower()
        if source_key == "flatpak":
            return "flatpak"
        if source_key == "manual":
            return "manual"

        cats = desktop_categories.lower()
        if "settings" in cats or "preferences" in cats:
            return "preferences"
        if "system" in cats or "administration" in cats:
            return "administration"
        if "audiovideo" in cats or "audio" in cats or "video" in cats:
            return "sound & video"
        if "office" in cats:
            return "office"
        if "network" in cats or "webbrowser" in cats or "email" in cats or "chat" in cats:
            return "internet"
        if "graphics" in cats:
            return "graphic"
        if "utility" in cats or "accessories" in cats:
            return "accessories"
        return "all apps"

    async def install_apps(self, apps: list[AppInfo], progress_callback=None) -> bool:
        """Install multiple applications with batch optimization.

        This is an alias for batch_install for compatibility with existing code.
        """
        return await self.batch_install(apps, progress_callback)

    async def batch_install(self, apps: list[AppInfo], progress_callback=None) -> bool:
        """Install multiple applications with batch optimization."""
        all_success = True

        # Group by package manager
        by_manager: dict[str, list[AppInfo]] = {}
        for app in apps:
            manager = await self._select_package_manager(app)
            if manager:
                manager_name = manager.name
                if manager_name not in by_manager:
                    by_manager[manager_name] = []
                by_manager[manager_name].append(app)
            else:
                log.error("No package manager found for %s", app.name)
                app.status = SetupStatus.FAILED
                all_success = False

        # Install by package manager
        for manager_name, manager_apps in by_manager.items():
            manager = self._package_managers.get(manager_name)
            if not manager:
                continue

            # Update status for all apps in this batch
            for app in manager_apps:
                app.status = SetupStatus.RUNNING

            # Install
            success = True
            for app in manager_apps:
                if progress_callback:
                    progress_callback(f"Installing {app.name}...", 0.0)

                app_success = await self.install_app(app, progress_callback)
                if not app_success:
                    success = False
                    all_success = False

            # Update batch status
            status = SetupStatus.COMPLETED if success else SetupStatus.FAILED
            for app in manager_apps:
                if app.status == SetupStatus.RUNNING:  # Only update if still running
                    app.status = status

        return all_success
