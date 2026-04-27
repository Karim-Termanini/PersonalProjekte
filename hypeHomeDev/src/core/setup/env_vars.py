"""HypeDevHome — Environment variable engine.

Manages a dedicated environment variables file and ensures shell integration.
"""

from __future__ import annotations

import base64
import logging
import shlex
from pathlib import Path

from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)

ENV_DIR = Path.home() / ".config/hypedevhome"
ENV_FILE = ENV_DIR / "env_vars.sh"
PROFILE_FILE = Path.home() / ".profile"
MARKER_START = "# >>> HypeDevHome Env Vars start >>>"
MARKER_END = "# <<< HypeDevHome Env Vars end <<<"


class EnvVarEngine:
    """Manage environment variable exports with a dedicated engine file."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor
        self._env_file = ENV_FILE
        self._profile_file = PROFILE_FILE
        self._env_dir = ENV_DIR
        self._env_dir.mkdir(parents=True, exist_ok=True)

    def read_env_file(self) -> str:
        """Read the managed environment variables file."""
        if not self._env_file.exists():
            return ""

        result = self._executor.run_sync(["cat", str(self._env_file)])
        if result.success:
            return result.stdout

        log.warning("Unable to read environment file: %s", result.stderr.strip())
        return ""

    def write_env_file(self, content: str) -> bool:
        """Write the managed environment variables file."""
        try:
            encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
            quoted_content = shlex.quote(encoded)
            command = [
                "bash",
                "-lc",
                (
                    "python3 - <<'PY'\n"
                    "import base64, pathlib\n"
                    f"path = pathlib.Path({shlex.quote(str(self._env_file))})\n"
                    f"path.parent.mkdir(parents=True, exist_ok=True)\n"
                    f"path.write_bytes(base64.b64decode({quoted_content}))\n"
                    "PY"
                ),
            ]

            result = self._executor.run_sync(command)
            if not result.success:
                log.error("Failed to write environment file: %s", result.stderr.strip())
                # Emit toast notification for error
                self._emit_error_toast(
                    "Failed to save environment variables", f"Error: {result.stderr.strip()}"
                )
                return False

            # Try to update profile
            profile_success = self.ensure_profile_source()
            if not profile_success:
                self._emit_warning_toast(
                    "Profile update warning",
                    "Environment variables saved but could not update shell profile",
                )

            return True
        except Exception as e:
            log.exception("Unexpected error writing environment file: %s", e)
            # Emit toast notification for unexpected error
            self._emit_error_toast(
                "Failed to save environment variables", f"Unexpected error: {e!s}"
            )
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

    def _emit_warning_toast(self, title: str, message: str) -> None:
        """Emit a warning toast notification via EventBus."""
        try:
            from core.state import AppState

            state = AppState.get()
            if state.event_bus:
                state.event_bus.emit(
                    "ui.notification", message=f"{title}: {message}", type="warning", timeout=8
                )
        except Exception:
            log.warning("Could not emit warning toast: EventBus not available")

    def ensure_profile_source(self) -> bool:
        """Ensure the user's profile sources the managed env vars file."""
        current = ""
        if self._profile_file.exists():
            current = self._profile_file.read_text(encoding="utf-8", errors="ignore")

        source_line = f'if [ -f "{self._env_file}" ]; then\n  . "{self._env_file}"\nfi\n'
        if source_line.strip() in current:
            return True

        marker_block = f"{MARKER_START}\n{source_line}{MARKER_END}\n"
        if MARKER_START in current and MARKER_END in current:
            start = current.index(MARKER_START)
            end = current.index(MARKER_END) + len(MARKER_END)
            current = current[:start] + marker_block + current[end:]
        else:
            current += "\n" + marker_block

        try:
            self._profile_file.write_text(current, encoding="utf-8")
            return True
        except OSError as exc:
            log.error("Failed to update profile file: %s", exc)
            return False

    def get_profile_source_status(self) -> bool:
        """Return True if the managed env file is sourced from ~/.profile."""
        if not self._profile_file.exists():
            return False

        current = self._profile_file.read_text(encoding="utf-8", errors="ignore")
        return MARKER_START in current and MARKER_END in current

    def get_env_file_path(self) -> str:
        """Return the path to the managed environment variables file."""
        return str(self._env_file)

    def get_profile_path(self) -> str:
        """Return the shell profile path used for sourcing."""
        return str(self._profile_file)
