"""HypeDevHome — Persistent Activity Logging System.

Records maintenance activities, snapshots, and audits to a permanent JSON file.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

log = logging.getLogger(__name__)


class ActivityLogger:
    """Handles permanent storage of application maintenance activities."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        """Initialize the activity logger.

        Args:
            log_path: Path to activity.json. If None, uses XDG_DATA_HOME.
        """
        if log_path:
            self._log_path = Path(log_path)
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            self._log_path = Path(xdg_data) / "hypedevhome" / "activity.json"

        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        # Ensure file exists
        if not self._log_path.exists():
            self._save_activities([])

        log.info("ActivityLogger initialized at %s", self._log_path)

    def log_event(self, event_name: str, status: str = "info", **kwargs: Any) -> None:
        """Record an event to the activity log.

        Args:
            event_name: Name of the event (e.g. 'snapshot.created')
            status: Status of the event ('success', 'failed', 'info')
            kwargs: Additional event details
        """
        activity = {
            "timestamp": datetime.now().isoformat(),
            "event": event_name,
            "status": status,
            "details": kwargs,
        }

        with self._lock:
            activities = self._load_activities()
            activities.insert(0, activity)  # Newest first

            # Keep last 1000 items
            if len(activities) > 1000:
                activities = activities[:1000]

            self._save_activities(activities)

        log.debug("Activity logged: %s (%s)", event_name, status)

    def get_activities(
        self, limit: int = 50, event_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Retrieve recent activities.

        Args:
            limit: Maximum number of records to return.
            event_filter: Optional substring to filter event names.

        Returns:
            List of activity dictionaries.
        """
        with self._lock:
            activities = self._load_activities()

        if event_filter:
            activities = [a for a in activities if event_filter in a["event"]]

        return activities[:limit]

    def clear_logs(self) -> None:
        """Permanently clear the activity log."""
        with self._lock:
            self._save_activities([])
        log.info("Activity log cleared")

    def _load_activities(self) -> list[dict[str, Any]]:
        """Load activities from disk. Must be called within a lock."""
        try:
            if not self._log_path.exists():
                return []
            content = self._log_path.read_text(encoding="utf-8")
            if not content:
                return []
            data = json.loads(content)
            if isinstance(data, list):
                return cast(list[dict[str, Any]], data)
            return []
        except Exception as e:
            log.error("Failed to load activities: %s", e)
            return []

    def _save_activities(self, activities: list[dict[str, Any]]) -> None:
        """Save activities to disk. Must be called within a lock."""
        try:
            temp_path = self._log_path.with_suffix(".tmp")
            temp_path.write_text(json.dumps(activities, indent=2), encoding="utf-8")
            temp_path.replace(self._log_path)
        except Exception as e:
            log.error("Failed to save activities: %s", e)
