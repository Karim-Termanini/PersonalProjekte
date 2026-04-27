"""HypeDevHome — Host Executor.

Utility to safely execute commands on the host system, escaping the
Flatpak sandbox if necessary via flatpak-spawn.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class CommandResult:
    """Result of a host command execution."""

    stdout: str
    stderr: str
    returncode: int
    command: list[str]

    @property
    def success(self) -> bool:
        """Return True if command succeeded (return code 0)."""
        return self.returncode == 0


class HostExecutor:
    """Executes commands on the host system.

    If running inside a Flatpak container, automatically wraps commands
    with `flatpak-spawn --host`.
    """

    def __init__(self) -> None:
        self.is_flatpak = os.path.exists("/.flatpak-info")
        self.has_pkexec = shutil.which("pkexec") is not None
        self.has_sudo = shutil.which("sudo") is not None
        if self.is_flatpak:
            log.info("Flatpak environment detected, using flatpak-spawn.")

    def _prepare_command(self, cmd: list[str], root: bool = False) -> list[str]:
        """Wrap the command correctly depending on execution context."""
        actual_cmd = cmd.copy()

        if root:
            if self.has_pkexec:
                actual_cmd = ["pkexec", *actual_cmd]
            elif self.has_sudo:
                actual_cmd = ["sudo", *actual_cmd]
            else:
                log.warning("No privilege escalation tool available; running without root.")
                # Emit instructional toast about missing pkexec
                self._emit_pkexec_missing_toast()

        if self.is_flatpak:
            actual_cmd = ["flatpak-spawn", "--host", *actual_cmd]

        return actual_cmd

    def _emit_pkexec_missing_toast(self) -> None:
        """Emit an instructional toast about missing pkexec."""
        try:
            from core.state import AppState

            state = AppState.get()
            if state.event_bus:
                state.event_bus.emit(
                    "ui.notification",
                    message="pkexec not found. Install 'polkit' package for privileged operations.",
                    type="warning",
                    timeout=15,
                )
        except Exception:
            log.warning("Could not emit pkexec missing toast: EventBus not available")

    async def run_async(
        self,
        cmd: list[str],
        root: bool = False,
        timeout: float | None = None,
        cwd: str | None = None,
    ) -> CommandResult:
        """Run a command asynchronously.

        Args:
            cmd: List of strings forming the command.
            root: If True, execute with pkexec.
            timeout: Optional timeout in seconds.

        Returns:
            CommandResult containing output and status.
        """
        full_cmd = self._prepare_command(cmd, root)
        log.debug("Executing async: %s", " ".join(full_cmd))

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            # Wait for completion
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

            result = CommandResult(
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                returncode=process.returncode or 0,
                command=full_cmd,
            )

            if not result.success:
                log.warning(
                    "Command failed (%d): %s\nStderr: %s",
                    result.returncode,
                    " ".join(full_cmd),
                    result.stderr.strip(),
                )

            return result

        except TimeoutError:
            log.error("Command timed out: %s", " ".join(full_cmd))
            # Try to kill it
            try:
                if process:
                    process.kill()
            except Exception:
                pass
            return CommandResult("", "Execution timed out.", -1, full_cmd)
        except Exception as e:
            log.exception("Error executing %s: %s", full_cmd, e)
            return CommandResult("", str(e), -1, full_cmd)

    async def run_async_streaming(
        self,
        cmd: list[str],
        *,
        root: bool = False,
        timeout: float | None = None,
        cwd: str | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> CommandResult:
        """Run command and invoke ``on_line`` for each stdout/stderr line (for progress parsing)."""
        full_cmd = self._prepare_command(cmd, root)
        log.debug("Executing streaming: %s", " ".join(full_cmd))

        try:
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
        except Exception as e:
            log.exception("Error starting %s: %s", full_cmd, e)
            return CommandResult("", str(e), -1, full_cmd)

        out_parts: list[str] = []
        err_parts: list[str] = []

        async def _drain(reader: asyncio.StreamReader, parts: list[str]) -> None:
            while True:
                line = await reader.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace")
                parts.append(text)
                if on_line:
                    on_line(text.rstrip("\n"))

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    _drain(process.stdout, out_parts),
                    _drain(process.stderr, err_parts),
                ),
                timeout=timeout,
            )
        except TimeoutError:
            log.error("Streaming command timed out: %s", " ".join(full_cmd))
            try:
                process.kill()
            except Exception:
                pass
            return CommandResult("", "Execution timed out.", -1, full_cmd)
        except Exception as e:
            log.exception("Streaming error %s: %s", full_cmd, e)
            return CommandResult("", str(e), -1, full_cmd)

        rc = await process.wait()
        return CommandResult(
            stdout="".join(out_parts),
            stderr="".join(err_parts),
            returncode=rc if rc is not None else -1,
            command=full_cmd,
        )

    def run_sync(
        self,
        cmd: list[str],
        root: bool = False,
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> CommandResult:
        """Run a command synchronously. Use only when asyncio is unavailable/in threads.

        Args:
            cmd: List of strings forming the command.
            root: If True, execute with pkexec.

        Returns:
            CommandResult containing output and status.
        """
        full_cmd = self._prepare_command(cmd, root)
        log.debug("Executing sync: %s", " ".join(full_cmd))

        try:
            process = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                timeout=timeout,
            )

            result = CommandResult(
                stdout=process.stdout,
                stderr=process.stderr,
                returncode=process.returncode,
                command=full_cmd,
            )

            if not result.success:
                log.warning(
                    "Command failed (%d): %s\nStderr: %s",
                    result.returncode,
                    " ".join(full_cmd),
                    result.stderr.strip(),
                )

            return result

        except subprocess.TimeoutExpired:
            log.error("Sync command timed out: %s", " ".join(full_cmd))
            return CommandResult("", "Execution timed out.", -1, full_cmd)
        except Exception as e:
            log.exception("Error executing sync %s: %s", full_cmd, e)
            return CommandResult("", str(e), -1, full_cmd)

    async def get_fs_type(self, path: str) -> str | None:
        """Detect the filesystem type for a given path using 'df -T' or 'stat'."""
        # Ensure path exists or check parent
        parent = os.path.dirname(os.path.abspath(os.path.expanduser(path)))

        # Use df -T to get the filesystem type
        result = await self.run_async(["df", "-T", parent])
        if result.success and result.stdout:
            lines = result.stdout.splitlines()
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 2:
                    return parts[1]  # The 'Type' column
        return None
