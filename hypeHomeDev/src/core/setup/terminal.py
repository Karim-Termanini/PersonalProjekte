"""HypeDevHome — Terminal Launching Service.

Handles detection of system terminals and launching commands (like distrobox enter)
in a new terminal window.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.state import AppState

log = logging.getLogger(__name__)


class TerminalLauncher:
    """Detects and launches commands in the preferred system terminal."""

    def __init__(self, state: AppState | None = None) -> None:
        self._state = state
        self._terminal_command: str | None = None

    def _detect_terminal(self) -> str:
        """Detect the best terminal to use based on environment and config."""
        # 1. Check for manual override in config
        if self._state and self._state.config:
            override = self._state.config.get("terminal")
            if isinstance(override, str) and override and shutil.which(override.split()[0]):
                log.debug("Using configured terminal override: %s", override)
                return override

        # 2. Try xdg-terminal-exec (the modern standard)
        if shutil.which("xdg-terminal-exec"):
            return "xdg-terminal-exec"

        # 3. Detect Desktop Environment
        de = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()

        if "GNOME" in de:
            if shutil.which("gnome-terminal"):
                return "gnome-terminal --"
            if shutil.which("kgx"):  # GNOME Console
                return "kgx -e"

        if ("KDE" in de or "PLASMA" in de) and shutil.which("konsole"):
            return "konsole -e"

        if "XFCE" in de and shutil.which("xfce4-terminal"):
            return "xfce4-terminal -e"

        # 4. Fallback hierarchy
        fallbacks = [
            ("alacritty", "-e"),
            ("kitty", "--"),
            ("wezterm", "start --"),
            ("terminology", "-e"),
            ("xterm", "-e"),
        ]

        for term, flag in fallbacks:
            if shutil.which(term):
                return f"{term} {flag}"

        return ""

    def launch(self, command: list[str], title: str | None = None) -> bool:
        """Launch a command in a new terminal window.

        Args:
            command: The command and arguments to run.
            title: Optional title for the terminal window.

        Returns:
            True if the terminal was successfully started.
        """
        term_cmd = self._detect_terminal()
        if not term_cmd:
            log.error("No suitable terminal found on the system.")
            return False

        # Build final command
        # term_cmd might contain flags (e.g., "gnome-terminal --")
        parts = term_cmd.split()
        full_command = parts + command

        try:
            log.info("Launching terminal: %s", " ".join(full_command))
            # Run detached
            subprocess.Popen(
                full_command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception as e:
            log.error("Failed to launch terminal: %s", e)
            return False

    def launch_distrobox(self, container_name: str) -> bool:
        """Convenience method to enter a Distrobox container in a new terminal."""
        return self.launch(
            ["distrobox", "enter", container_name], title=f"HypeDev - {container_name}"
        )
