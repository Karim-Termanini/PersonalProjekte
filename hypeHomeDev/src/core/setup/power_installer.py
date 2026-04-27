"""HypeDevHome — Power Installer Orchestrator.

Orchestrates multi-stage system setups based on Outcome Profiles.
Coordinates PackageInstaller, SystemdManager, and DockerManager.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from core.setup.distro_detector import DistroDetector
from core.setup.models import AppInfo, SetupStatus
from core.setup.package_catalog import PackageCatalog
from core.setup.package_installer import PackageInstaller
from core.setup.systemd_manager import SystemdManager

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class OutcomeProfile:
    """A collection of setup steps to achieve a specific outcome."""
    id: str
    name: str
    description: str
    icon: str
    host_packages: list[str] = field(default_factory=list)
    npm_packages: list[str] = field(default_factory=list)
    services: list[str] = field(default_factory=list)
    docker_containers: list[dict[str, Any]] = field(default_factory=list)
    ai_models: list[str] = field(default_factory=list)


def _docker_run_argv(container: dict[str, Any]) -> list[str] | None:
    """Build ``docker run -d`` argv from a profile container dict; returns None if no image."""
    image = container.get("image")
    if not image:
        return None
    c_name = str(container.get("name", "unnamed"))
    cmd: list[str] = ["docker", "run", "-d", "--name", c_name, "--restart", "always"]
    for port in container.get("ports", []):
        if isinstance(port, str) and port.strip():
            cmd.extend(["-p", port.strip()])
    for e in container.get("env", []):
        if isinstance(e, str) and "=" in e:
            cmd.extend(["-e", e.strip()])
    for vol in container.get("volumes", []):
        if isinstance(vol, str) and vol.strip():
            cmd.extend(["-v", vol.strip()])
    cmd.append(str(image))
    return cmd


class PowerInstaller:
    """Orchestrator for bulk system setup profiles."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor
        self._package_installer = PackageInstaller(executor)
        self._systemd = SystemdManager()
        self._profiles: dict[str, OutcomeProfile] = {}
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load outcome profiles from JSON."""
        profiles_path = Path(__file__).parent / "outcome_profiles.json"
        if not profiles_path.exists():
            log.warning("Outcome profiles center not found: %s", profiles_path)
            return

        try:
            data = json.loads(profiles_path.read_text(encoding="utf-8"))
            keys = {f.name for f in fields(OutcomeProfile)}
            for p in data.get("profiles", []):
                if not isinstance(p, dict):
                    continue
                profile = OutcomeProfile(**{k: v for k, v in p.items() if k in keys})
                self._profiles[profile.id] = profile
            log.info("Loaded %d outcome profiles", len(self._profiles))
        except Exception:
            log.exception("Failed to load outcome profiles from %s", profiles_path)

    def get_profiles(self) -> list[OutcomeProfile]:
        """Return all available setup profiles."""
        return list(self._profiles.values())

    async def run_profile(
        self, 
        profile_id: str, 
        progress_callback: Callable[[str, float, str], None] | None = None
    ) -> bool:
        """Execute a full outcome profile.
        
        Args:
            profile_id: ID of the profile to run.
            progress_callback: (step_name, percentage, status_text) -> None
        """
        profile = self._profiles.get(profile_id)
        if not profile:
            log.error("Profile not found: %s", profile_id)
            return False

        log.info("Starting Power-Build: %s", profile.name)
        total_steps = (
            len(profile.host_packages) + 
            len(profile.services) + 
            len(profile.docker_containers) +
            (1 if profile.npm_packages else 0)
        )
        completed_steps = 0

        def _update(text: str, step_inc: int = 0):
            nonlocal completed_steps
            completed_steps += step_inc
            if progress_callback:
                pct = (completed_steps / total_steps) * 100 if total_steps > 0 else 100
                progress_callback(profile.name, pct, text)

        # 1. Initialize installers
        _update("Preparing environment...")
        await self._package_installer.initialize()
        distro_info = await DistroDetector(self._executor).detect()

        # 2. Host Packages
        catalog = PackageCatalog()
        await catalog.load()
        
        for pkg_id in profile.host_packages:
            _update(f"Installing {pkg_id}...")
            app_info = catalog.get_package_for_distro(pkg_id, distro_info)
            if app_info:
                success = await self._package_installer.install_app(app_info)
                if not success:
                    log.warning("Failed to install host package: %s", pkg_id)
            else:
                # Fallback to direct package name if not in catalog
                log.info("Package %s not in catalog, attempting direct install", pkg_id)
                from core.setup.models import AppInfo
                direct_app = AppInfo(id=pkg_id, name=pkg_id, description="", icon="", package_name=pkg_id)
                await self._package_installer.install_app(direct_app)
            completed_steps += 1
            _update(f"Finished {pkg_id}")

        # 3. NPM Packages
        if profile.npm_packages:
            _update(f"Installing NPM tools: {', '.join(profile.npm_packages)}...")
            cmd = ["npm", "install", "-g"] + profile.npm_packages
            res = await self._executor.run_async(cmd)
            if not res.success:
                log.warning("NPM globals installation had issues")
            completed_steps += 1

        # 4. Host Services
        for svc in profile.services:
            _update(f"Activating service: {svc}...")
            self._systemd.enable_unit(svc)
            self._systemd.start_unit(svc)
            completed_steps += 1

        # 5. Docker Containers
        for container in profile.docker_containers:
            if not isinstance(container, dict):
                continue
            c_name = container.get("name", "unnamed")
            _update(f"Starting container: {c_name}...")
            docker_cmd = _docker_run_argv(container)
            if not docker_cmd:
                log.warning("Skipping container %s: no image in profile", c_name)
                continue
            await self._executor.run_async(["docker", "rm", "-f", str(c_name)])
            res = await self._executor.run_async(docker_cmd)
            if not res.success:
                log.warning("Docker container start failed: %s", c_name)
            completed_steps += 1

        _update("System build complete!", step_inc=0)
        if progress_callback:
            progress_callback(profile.name, 100.0, "Complete")
        log.info("Power-Build '%s' finished.", profile.name)
        return True

    async def run_all_profiles(
        self,
        progress_callback: Callable[[str, float, str], None] | None = None,
        *,
        profile_ids: list[str] | None = None,
    ) -> bool:
        """Run several profiles in order (power mode: full stack).

        If ``profile_ids`` is ``None``, every loaded profile runs in JSON order.
        If ``profile_ids`` is an empty list, nothing runs and this returns ``True``.
        """
        if profile_ids is not None and len(profile_ids) == 0:
            return True
        if profile_ids is None:
            ordered = [p.id for p in self.get_profiles()]
        else:
            ordered = [pid for pid in profile_ids if pid in self._profiles]
        if not ordered:
            log.warning("run_all_profiles: no valid profile ids to execute")
            return False

        n = len(ordered)
        for i, pid in enumerate(ordered):
            prof = self._profiles[pid]
            idx = i
            pname = prof.name

            def _wrap_cb(
                _step_name: str,
                pct: float,
                status: str,
                *,
                _idx: int = idx,
                _pname: str = pname,
            ) -> None:
                if not progress_callback:
                    return
                base = (_idx / n) * 100.0
                span = (1.0 / n) * 100.0
                overall = base + max(0.0, min(100.0, pct)) / 100.0 * span
                progress_callback(f"{_pname} ({_idx + 1}/{n})", overall, status)

            ok = await self.run_profile(pid, _wrap_cb)
            if not ok:
                log.error("run_all_profiles: profile %r failed, stopping", pid)
                return False

        if progress_callback:
            progress_callback("All profiles", 100.0, "Complete")
        log.info("run_all_profiles: finished %d profile(s)", n)
        return True
