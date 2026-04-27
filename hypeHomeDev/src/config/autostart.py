"""HypeDevHome — Auto-start integration.

Provides auto-start functionality via Flatpak portals and desktop entries.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from config.manager import ConfigManager

log = logging.getLogger(__name__)


class AutoStartManager:
    """Manage application auto-start on login."""

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config = config_manager
        self._desktop_entry_path = self._get_desktop_entry_path()
        log.debug("AutoStartManager initialized")

    def is_available(self) -> bool:
        """Check if auto-start is available on this system."""
        # Check for Flatpak portal
        try:
            import gi

            gi.require_version("Xdp", "1.0")
            from gi.repository import Xdp

            portal = cast(Any, Xdp.Portal())
            return bool(portal.is_available())
        except (ImportError, ValueError, AttributeError):
            pass

        # Fallback: check for desktop entry directory
        return self._desktop_entry_path is not None

    def is_enabled(self) -> bool:
        """Check if auto-start is currently enabled."""
        if not self.is_available():
            return False

        # Check config first
        if not self.config.get("auto_start", False):
            return False

        # Check if desktop entry exists
        return bool(self._desktop_entry_path and self._desktop_entry_path.exists())

    def enable(self) -> bool:
        """Enable auto-start on login.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available():
            log.error("Auto-start not available on this system")
            return False

        try:
            # First try Flatpak portal
            if self._try_flatpak_portal(enable=True):
                self.config.set("auto_start", True)
                log.info("Auto-start enabled via Flatpak portal")
                return True

            # Fallback to desktop entry
            if self._create_desktop_entry():
                self.config.set("auto_start", True)
                log.info("Auto-start enabled via desktop entry")
                return True

            log.error("Failed to enable auto-start")
            return False

        except Exception as e:
            log.error("Error enabling auto-start: %s", e)
            return False

    def disable(self) -> bool:
        """Disable auto-start on login.

        Returns:
            True if successful, False otherwise.
        """
        if not self.is_available():
            log.error("Auto-start not available on this system")
            return False

        try:
            # First try Flatpak portal
            if self._try_flatpak_portal(enable=False):
                self.config.set("auto_start", False)
                log.info("Auto-start disabled via Flatpak portal")
                return True

            # Fallback to desktop entry removal
            if self._remove_desktop_entry():
                self.config.set("auto_start", False)
                log.info("Auto-start disabled via desktop entry removal")
                return True

            log.error("Failed to disable auto-start")
            return False

        except Exception as e:
            log.error("Error disabling auto-start: %s", e)
            return False

    def toggle(self) -> bool:
        """Toggle auto-start state.

        Returns:
            True if successful, False otherwise.
        """
        if self.is_enabled():
            return self.disable()
        else:
            return self.enable()

    # ── Internal methods ────────────────────────────────

    def _get_desktop_entry_path(self) -> Path | None:
        """Get the path for the auto-start desktop entry."""
        # Try XDG autostart directory
        xdg_config_home = Path.home() / ".config"
        if "XDG_CONFIG_HOME" in os.environ:
            xdg_config_home = Path(os.environ["XDG_CONFIG_HOME"])

        autostart_dir = xdg_config_home / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)

        return autostart_dir / "com.github.hypedevhome.desktop"

    def _try_flatpak_portal(self, enable: bool) -> bool:
        """Try to use Flatpak portal for auto-start.

        Args:
            enable: True to enable, False to disable.

        Returns:
            True if portal was used, False otherwise.
        """
        try:
            import gi

            gi.require_version("Xdp", "1.0")
            from gi.repository import GLib, Xdp

            portal = Xdp.Portal()

            # Create a main loop for async operation
            loop = GLib.MainLoop()
            result = [None]

            def callback(portal_obj, task, user_data):
                try:
                    success = portal_obj.set_autostart_finish(task)
                    result[0] = success
                except Exception as e:
                    log.error("Portal callback error: %s", e)
                    result[0] = False
                finally:
                    loop.quit()

            # Note: This is a simplified version. In a real app,
            # we would need proper async handling.
            cast(Any, portal).set_autostart(
                parent=None,
                identifier="com.github.hypedevhome",
                enable=enable,
                cancellable=None,
                callback=callback,
                user_data=None,
            )

            # Run the loop briefly (simplified)
            context = loop.get_context()
            context.iteration(True)

            return result[0] or False

        except (ImportError, ValueError, AttributeError) as e:
            log.debug("Flatpak portal not available: %s", e)
            return False

    def _create_desktop_entry(self) -> bool:
        """Create a desktop entry for auto-start.

        Returns:
            True if successful, False otherwise.
        """
        if not self._desktop_entry_path:
            return False

        try:
            # Read the main desktop entry
            current_file_path = Path(__file__).resolve()
            # project_root/src/config/autostart.py -> data is in project_root/data
            main_desktop_path = (
                current_file_path.parent.parent.parent / "data" / "com.github.hypedevhome.desktop"
            )
            if not main_desktop_path.exists():
                log.error("Main desktop entry not found: %s", main_desktop_path)
                return False

            desktop_content = main_desktop_path.read_text(encoding="utf-8")

            # Modify for auto-start (add Hidden=false and remove OnlyShowIn if present)
            lines = desktop_content.splitlines()
            modified_lines = []

            for line in lines:
                if line.startswith("Hidden="):
                    modified_lines.append("Hidden=false")
                elif line.startswith("OnlyShowIn="):
                    # Remove or comment out OnlyShowIn for auto-start
                    modified_lines.append(f"# {line}")
                else:
                    modified_lines.append(line)

            # Ensure Hidden=false is present
            if not any(line.startswith("Hidden=") for line in modified_lines):
                # Find the [Desktop Entry] section and insert after it
                for i, line in enumerate(modified_lines):
                    if line.strip() == "[Desktop Entry]":
                        modified_lines.insert(i + 1, "Hidden=false")
                        break

            # Write the auto-start desktop entry
            self._desktop_entry_path.write_text("\n".join(modified_lines), encoding="utf-8")
            log.debug("Auto-start desktop entry created: %s", self._desktop_entry_path)
            return True

        except Exception as e:
            log.error("Error creating desktop entry: %s", e)
            return False

    def _remove_desktop_entry(self) -> bool:
        """Remove the auto-start desktop entry.

        Returns:
            True if successful, False otherwise.
        """
        if not self._desktop_entry_path or not self._desktop_entry_path.exists():
            return True  # Already removed

        try:
            self._desktop_entry_path.unlink()
            log.debug("Auto-start desktop entry removed: %s", self._desktop_entry_path)
            return True
        except Exception as e:
            log.error("Error removing desktop entry: %s", e)
            return False
