"""HypeDevHome — Desktop Configuration Manager.

Applies GNOME-style settings via GSettings when schemas are available (Fedora, Ubuntu GNOME, etc.).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio  # noqa: E402

from core.utils.base import BaseUtilityManager  # noqa: E402

log = logging.getLogger(__name__)


def _try_settings(schema_id: str) -> Gio.Settings | None:
    """Return a GSettings instance or None if the schema is missing."""
    try:
        return Gio.Settings.new(schema_id)
    except Exception:
        log.debug("GSettings schema unavailable: %s", schema_id)
        return None


def _xdg_desktop_tokens() -> set[str]:
    """Uppercase tokens from XDG_CURRENT_DESKTOP / XDG_SESSION_DESKTOP (e.g. KDE, GNOME)."""
    raw = (
        os.environ.get("XDG_CURRENT_DESKTOP", "")
        or os.environ.get("XDG_SESSION_DESKTOP", "")
        or os.environ.get("DESKTOP_SESSION", "")
    )
    tokens: set[str] = set()
    for part in re.split(r"[\s:]+", raw):
        p = part.strip().upper()
        if p:
            tokens.add(p)
    return tokens


def describe_session_for_hints() -> str:
    """Short, user-facing label for the current desktop (for inline hints)."""
    t = _xdg_desktop_tokens()
    if "KDE" in t or "PLASMA" in t:
        return "KDE Plasma"
    if "GNOME" in t:
        return "GNOME"
    if "XFCE" in t:
        return "Xfce"
    if "MATE" in t:
        return "MATE"
    if "CINNAMON" in t:
        return "Cinnamon"
    if "BUDGIE" in t:
        return "Budgie"
    if "COSMIC" in t or "POP-COSMIC" in t:
        return "COSMIC"
    if "UNITY" in t:
        return "Unity"
    if "LXQT" in t or "LXQT-WAYLAND-SESSION" in t:
        return "LXQt"
    if "I3" in t or "SWAY" in t or "HYPRLAND" in t:
        return "a tiling Wayland session"
    if t:
        return "this desktop (" + ", ".join(sorted(t)).lower() + ")"
    return "this desktop"


class DesktopManager(BaseUtilityManager):
    """Manages desktop environment settings (GNOME interface + mutter when present)."""

    def __init__(self) -> None:
        super().__init__()
        self._iface = _try_settings("org.gnome.desktop.interface")
        self._mutter = _try_settings("org.gnome.mutter")

    async def initialize(self) -> bool:
        """Detect DE and mark ready (settings objects are resolved in __init__)."""
        self._initialized = True
        return True

    def get_settings(self) -> dict[str, Any]:
        """Return current desktop settings snapshot for diagnostics."""
        return {
            "gnome_interface": self._iface is not None,
            "gnome_mutter": self._mutter is not None,
            "theme_index": self.get_theme_index(),
            "font_spin": self.get_font_size_spin(),
            "animations": self.get_animations_enabled(),
            "edge_tiling": self.get_edge_tiling_enabled(),
        }

    # --- Theme (GNOME 42+ color-scheme) — Combo: Dark, Light, System Default ---
    def get_theme_index(self) -> int:
        """Map color-scheme to row index: 0 Dark, 1 Light, 2 System."""
        if not self._iface:
            return 2
        try:
            cs = self._iface.get_string("color-scheme")
        except Exception:
            return 2
        return {"prefer-dark": 0, "prefer-light": 1, "default": 2}.get(cs, 2)

    def set_theme_index(self, index: int) -> bool:
        if not self._iface:
            log.warning("org.gnome.desktop.interface not available; theme not applied")
            return False
        key = {0: "prefer-dark", 1: "prefer-light", 2: "default"}.get(index, "default")
        try:
            self._iface.set_string("color-scheme", key)
            return True
        except Exception as e:
            log.warning("Could not set color-scheme: %s", e)
            return False

    # --- Font scaling (text-scaling-factor 1.0 ≈ “11” in the UI) ---
    def get_font_size_spin(self) -> int:
        if not self._iface:
            return 11
        try:
            f = self._iface.get_double("text-scaling-factor")
        except Exception:
            return 11
        v = round(11.0 * f)
        return max(8, min(24, v))

    def set_font_size_spin(self, n: int) -> bool:
        if not self._iface:
            log.warning("org.gnome.desktop.interface not available; font scaling not applied")
            return False
        factor = max(0.5, min(2.0, n / 11.0))
        try:
            self._iface.set_double("text-scaling-factor", factor)
            return True
        except Exception as e:
            log.warning("Could not set text-scaling-factor: %s", e)
            return False

    def get_animations_enabled(self) -> bool:
        if not self._iface:
            return True
        try:
            return self._iface.get_boolean("enable-animations")
        except Exception:
            return True

    def set_animations_enabled(self, enabled: bool) -> bool:
        if not self._iface:
            return False
        try:
            self._iface.set_boolean("enable-animations", enabled)
            return True
        except Exception as e:
            log.warning("Could not set enable-animations: %s", e)
            return False

    def get_edge_tiling_enabled(self) -> bool:
        """Window snapping / edge tiling (org.gnome.mutter)."""
        if not self._mutter:
            return False
        try:
            return self._mutter.get_boolean("edge-tiling")
        except Exception:
            return False

    def set_edge_tiling_enabled(self, enabled: bool) -> bool:
        if not self._mutter:
            log.warning("org.gnome.mutter not available; tiling toggle not applied")
            return False
        try:
            self._mutter.set_boolean("edge-tiling", enabled)
            return True
        except Exception as e:
            log.warning("Could not set edge-tiling: %s", e)
            return False

    async def apply_setting(self, key: str, value: Any) -> bool:
        """Legacy hook — prefer the typed setters above."""
        log.debug("apply_setting(%s, %s)", key, value)
        return True

    def get_status(self) -> dict[str, Any]:
        return {
            "initialized": self._initialized,
            "has_gnome_interface": self._iface is not None,
            "has_gnome_mutter": self._mutter is not None,
            "session_label": describe_session_for_hints(),
        }

    def desktop_hint_paragraphs(self) -> list[str]:
        """Human-readable explanations when GSettings backends are missing (KDE, minimal installs, etc.)."""
        paragraphs: list[str] = []
        session = describe_session_for_hints()
        has_iface = self._iface is not None
        has_mutter = self._mutter is not None

        if not has_iface:
            paragraphs.append(
                "Theme, font scaling, and UI animations here talk to GNOME's "
                "org.gnome.desktop.interface schema. That schema is missing or not used on "
                f"{session}, and on many non-GNOME distros (KDE, Xfce, COSMIC, minimal spins). "
                "Use your distribution's own Settings / Appearance / Fonts instead—changes here "
                "will not apply system-wide."
            )
        if not has_mutter:
            paragraphs.append(
                "Edge tiling / snap uses org.gnome.mutter (standard on GNOME on Fedora, "
                "Ubuntu, etc.). Without it—typical on KDE Plasma, other desktops, or headless "
                "installs—the toggle below has no effect. Configure tiling in your desktop's "
                "window or tiling settings instead."
            )

        return paragraphs
