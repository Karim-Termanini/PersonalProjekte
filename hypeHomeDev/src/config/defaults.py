"""HypeDevHome — Default configuration constants."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# ── Directories ─────────────────────────────────────────
CONFIG_DIR: Path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "dev-home"

DATA_DIR: Path = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "dev-home"
)

# ── Application defaults ────────────────────────────────
DEFAULT_REFRESH_INTERVAL: float = 2.0  # seconds
DEFAULT_THEME: str = "system"  # "system" | "light" | "dark"
DEFAULT_AUTO_START: bool = False
DEFAULT_CONFIRM_QUIT: bool = True
DEFAULT_ANIMATIONS_ENABLED: bool = True

# GitHub dashboard widgets + background monitor (seconds)
DEFAULT_GITHUB_REFRESH_INTERVAL: float = 30.0

# ── Dashboard defaults ──────────────────────────────────
DEFAULT_DASHBOARD_LAYOUT: list[dict[str, Any]] = [
    {"id": "stack_monitor"},
    {"id": "hypesync_status"},
    {"id": "cpu"},
    {"id": "memory"},
    {"id": "network"},
    {"id": "gpu"},
    {"id": "ssh"},
    {"id": "clock"},
]

# ── Config file ─────────────────────────────────────────
CONFIG_FILENAME: str = "config.json"

# ── Logging ─────────────────────────────────────────────
LOG_FILENAME: str = "dev-home.log"
LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT: int = 5
LOG_FORMAT: str = "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
