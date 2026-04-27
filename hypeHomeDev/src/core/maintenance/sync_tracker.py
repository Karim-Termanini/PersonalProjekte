from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.events import EventBus
    from core.setup.git_ops import GitOperations
    from core.setup.host_executor import HostExecutor
    from core.setup.sync_manager import SyncManager

log = logging.getLogger(__name__)


@dataclass
class HypeSyncStatus:
    """Consolidated health and drift status for HypeSync."""

    last_sync_time: str | None = None
    last_sync_success: bool = False
    last_sync_error: str | None = None
    dotfiles_applied: bool = False
    secrets_bridged: bool = False
    drift_detected: bool = False
    drift_details: dict[str, Any] = field(default_factory=dict)
    sync_count: int = 0
    failure_count: int = 0

    # Legacy fields for backward compatibility with existing UI
    @property
    def dotfiles_clean(self) -> bool:
        return not self.drift_detected

    @property
    def dotfiles_behind_remote(self) -> bool:
        return bool(self.drift_details.get("git_behind", False))

    @property
    def secrets_injected(self) -> bool:
        return self.secrets_bridged


class HypeSyncStatusTracker:
    """Monitors dotfile repositories and secret injection state for drift."""

    def __init__(
        self,
        sync_manager: SyncManager | None = None,
        git_ops: GitOperations | None = None,
        dotfiles_path: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._sync_manager = sync_manager
        self._git_ops = git_ops
        self._dotfiles_path = dotfiles_path or (Path.home() / ".dotfiles")
        self._event_bus = event_bus
        self._status = HypeSyncStatus()

    def record_sync(
        self,
        success: bool,
        error: str | None = None,
        dotfiles_applied: bool = False,
        secrets_bridged: bool = False,
    ) -> None:
        """Record a sync operation result."""
        self._status.last_sync_time = datetime.now().isoformat()
        self._status.last_sync_success = success
        self._status.last_sync_error = error
        self._status.dotfiles_applied = dotfiles_applied
        self._status.secrets_bridged = secrets_bridged
        self._status.sync_count += 1

        if not success:
            self._status.failure_count += 1

        log.info(
            "Sync recorded: success=%s, dotfiles=%s, secrets=%s",
            success,
            dotfiles_applied,
            secrets_bridged,
        )

    async def get_status(self) -> HypeSyncStatus:
        """Get current sync status."""
        return self._status

    async def detect_drift(
        self,
        expected_config: dict[str, Any],
        executor: HostExecutor,
    ) -> bool:
        """Calculate current sync status and drift metrics."""
        log.debug("Detecting configuration drift...")
        drift_detected = False
        drift_details: dict[str, Any] = {}

        # 1. Check Git config drift
        if "git_user_name" in expected_config:
            result = await executor.run_async(["git", "config", "--global", "user.name"])
            if result.success and result.stdout.strip() != expected_config["git_user_name"]:
                drift_detected = True
                drift_details["git_user_name"] = {
                    "expected": expected_config["git_user_name"],
                    "actual": result.stdout.strip(),
                }

        # 2. Check for behind remote (if git_ops available)
        if self._git_ops and self._dotfiles_path.exists():
            info = await self._git_ops.get_repo_info(str(self._dotfiles_path))
            if info.is_git_repo and info.remote_url:
                # Check commits behind
                rev_log = await executor.run_async(
                    [
                        "git",
                        "-C",
                        str(self._dotfiles_path),
                        "rev-list",
                        "HEAD..origin/main",
                        "--count",
                    ]
                )
                if rev_log.success and rev_log.stdout.strip() != "0":
                    drift_detected = True
                    drift_details["git_behind"] = True
                    drift_details["commits_behind"] = rev_log.stdout.strip()

        # 3. Check SSH agent drift
        result = await executor.run_async(["ssh-add", "-l"])
        has_ssh = result.success
        if expected_config.get("ssh_expected", False) != has_ssh:
            drift_detected = True
            drift_details["ssh_agent"] = {
                "expected": expected_config.get("ssh_expected", False),
                "actual": has_ssh,
            }

        # Update internal state
        self._status.drift_detected = drift_detected
        self._status.drift_details = drift_details
        self._status.secrets_bridged = has_ssh  # Update bridging status based on live check

        if drift_detected:
            log.warning("Configuration drift detected: %s", drift_details)

        return drift_detected

    def _emit(self, event_name: str, **kwargs) -> None:
        """Emit an event to the EventBus if available."""
        if self._event_bus:
            # Standard namespace: maint.<event>
            self._event_bus.emit(f"maint.{event_name}", **kwargs)

    async def broadcast_status(self) -> None:
        """Emit status to the EventBus."""
        self._emit("sync.status", status=self._status)

    def reset(self) -> None:
        """Reset tracker to initial state."""
        self._status = HypeSyncStatus()
