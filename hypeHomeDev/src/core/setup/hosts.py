"""HypeDevHome — Secure hosts file manager.

Provides safe /etc/hosts editing with backups and privileged write support.
"""

from __future__ import annotations

import base64
import datetime
import logging
import os
import shlex
from pathlib import Path

from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)

HOSTS_FILE = "/etc/hosts"
BACKUP_DIR = Path.home() / ".local/share/hypedevhome/hosts-backups"


class HostFileManager:
    """Manage /etc/hosts safely with backups and restore support."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor
        self._backup_dir = BACKUP_DIR
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def read_hosts(self) -> str:
        """Return the current /etc/hosts content from the host."""
        result = self._executor.run_sync(["cat", HOSTS_FILE])
        if result.success:
            return result.stdout

        log.warning("Unable to read hosts file: %s", result.stderr.strip())
        return ""

    def write_hosts(self, content: str) -> bool:
        """Write content to /etc/hosts using a privileged host command."""
        try:
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            quoted_content = shlex.quote(encoded)
            command = [
                "bash",
                "-lc",
                (
                    "python3 - <<'PY'\n"
                    "import base64, pathlib\n"
                    f"path = pathlib.Path({shlex.quote(HOSTS_FILE)})\n"
                    f"path.write_bytes(base64.b64decode({quoted_content}))\n"
                    "PY"
                ),
            ]
            result = self._executor.run_sync(command, root=True)
            if not result.success:
                log.error("Failed to write hosts file: %s", result.stderr.strip())
                # Emit toast notification for error
                self._emit_error_toast(
                    "Failed to save hosts file", f"Error: {result.stderr.strip()}"
                )
                return False
            return result.success
        except Exception as e:
            log.exception("Unexpected error writing hosts file: %s", e)
            # Emit toast notification for unexpected error
            self._emit_error_toast("Failed to save hosts file", f"Unexpected error: {e!s}")
            return False

    def _emit_error_toast(self, title: str, message: str) -> None:
        """Emit an error toast notification via EventBus."""
        try:
            from core.state import AppState

            state = AppState.get()
            if state.event_bus:
                state.event_bus.emit(
                    "error.show-toast", message=f"{title}: {message}", type="error", timeout=10
                )
        except Exception:
            log.warning("Could not emit error toast: EventBus not available")

    def backup_hosts(self) -> str | None:
        """Backup /etc/hosts to the local backup directory and return the backup path."""
        self._backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self._backup_dir / f"hosts_{timestamp}.bak"
        result = self._executor.run_sync(
            ["cp", "-p", HOSTS_FILE, str(backup_path)],
            root=True,
        )
        if result.success:
            return str(backup_path)

        log.error("Failed to backup hosts file: %s", result.stderr.strip())
        return None

    def list_backups(self) -> list[str]:
        """List available hosts backups sorted by newest first."""
        if not self._backup_dir.exists():
            return []
        backups = [str(p) for p in self._backup_dir.glob("hosts_*.bak") if p.is_file()]
        return sorted(backups, reverse=True)

    def restore_backup(self, backup_path: str) -> bool:
        """Restore a hosts backup to /etc/hosts using privileged execution."""
        if not os.path.exists(backup_path):
            log.error("Hosts backup not found: %s", backup_path)
            return False

        result = self._executor.run_sync(
            ["cp", "-p", backup_path, HOSTS_FILE],
            root=True,
        )
        if not result.success:
            log.error("Failed to restore hosts backup: %s", result.stderr.strip())
        return result.success
