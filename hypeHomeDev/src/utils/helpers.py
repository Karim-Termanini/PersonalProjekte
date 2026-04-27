"""HypeDevHome — Common utility helpers.

A collection of small, pure-ish functions used across the codebase.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ── Path utilities ──────────────────────────────────────


def expand_path(path: str | Path) -> Path:
    """Expand ``~`` and environment variables, then resolve the path."""
    return Path(path).expanduser().resolve()


# ── JSON utilities ──────────────────────────────────────


def safe_load_json(path: str | Path, *, default: Any = None) -> Any:
    """Load JSON from *path*, returning *default* on any error.

    This is intentionally lenient — callers that need strict parsing
    should use ``json.load`` directly.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        log.debug("safe_load_json failed for %s: %s", path, exc)
        return default


# ── Formatting utilities ────────────────────────────────

_SIZE_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")


def human_readable_size(size_bytes: int | float) -> str:
    """Convert *size_bytes* to a human-friendly string (e.g. ``1.5 GiB``).

    Uses binary (IEC) units.
    """
    value = float(size_bytes)
    for unit in _SIZE_UNITS:
        if abs(value) < 1024.0:
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{value:.1f} EiB"


def format_timestamp(
    dt: datetime | None = None,
    *,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Return a formatted timestamp string.

    If *dt* is ``None`` the current UTC time is used.
    """
    if dt is None:
        dt = datetime.now(tz=UTC)
    return dt.strftime(fmt)
