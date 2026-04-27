"""HypeDevHome — Theme management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import gi

gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

if TYPE_CHECKING:
    from config.manager import ConfigManager

log = logging.getLogger(__name__)


class ThemeManager:
    """Manage application theme preferences."""

    def __init__(self, config_manager: ConfigManager) -> None:
        self.config = config_manager
        self._style_manager = Adw.StyleManager.get_default()
        log.debug("Theme manager initialized")

    def apply_theme(self) -> None:
        """Apply the configured theme to the application."""
        theme = self.config.get("theme", "system")

        if theme == "system":
            self._style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)
            log.debug("Theme set to: system (follows system preference)")
        elif theme == "light":
            self._style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
            log.debug("Theme set to: light")
        elif theme == "dark":
            self._style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
            log.debug("Theme set to: dark")
        else:
            log.warning("Unknown theme '%s', defaulting to system", theme)
            self._style_manager.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)

    def get_available_themes(self) -> list[tuple[str, str]]:
        """Get list of available themes with display names."""
        return [
            ("system", "System Default"),
            ("light", "Light"),
            ("dark", "Dark"),
        ]

    def get_current_theme(self) -> str:
        """Get the currently configured theme."""
        theme = self.config.get("theme", "system")
        return str(theme) if theme is not None else "system"

    def set_theme(self, theme: str) -> None:
        """Set and apply a new theme."""
        valid_themes = ["system", "light", "dark"]
        if theme not in valid_themes:
            log.error("Invalid theme: %s", theme)
            return

        self.config.set("theme", theme)
        self.apply_theme()
        log.info("Theme changed to: %s", theme)

    def is_dark_mode(self) -> bool:
        """Check if dark mode is currently active."""
        return bool(self._style_manager.get_dark())

    def get_system_theme(self) -> str:
        """Get the system's preferred theme."""
        return "dark" if self._style_manager.get_dark() else "light"
