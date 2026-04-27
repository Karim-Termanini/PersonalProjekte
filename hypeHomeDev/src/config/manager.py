"""HypeDevHome — Configuration manager.

Provides thread-safe JSON-based configuration management with
automatic directory creation, schema validation, and migration.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from config.defaults import (
    CONFIG_DIR,
    CONFIG_FILENAME,
    DEFAULT_ANIMATIONS_ENABLED,
    DEFAULT_AUTO_START,
    DEFAULT_CONFIRM_QUIT,
    DEFAULT_GITHUB_REFRESH_INTERVAL,
    DEFAULT_REFRESH_INTERVAL,
    DEFAULT_THEME,
)

log = logging.getLogger(__name__)

# Configuration schema version
CONFIG_SCHEMA_VERSION = 1

# Keys used as the top-level schema.  New settings should be added here
# alongside a corresponding default in ``_DEFAULT_CONFIG``.
_DEFAULT_CONFIG: dict[str, Any] = {
    "theme": DEFAULT_THEME,
    "refresh_interval": DEFAULT_REFRESH_INTERVAL,
    "auto_start": DEFAULT_AUTO_START,
    "confirm_quit": DEFAULT_CONFIRM_QUIT,
    "animations_enabled": DEFAULT_ANIMATIONS_ENABLED,
    "github_refresh_interval": DEFAULT_GITHUB_REFRESH_INTERVAL,
    # Internal metadata
    "_schema_version": CONFIG_SCHEMA_VERSION,
    "_created": None,
    "_modified": None,
}

# Schema validation rules
_CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
    "theme": {"type": str, "allowed": ["system", "light", "dark"]},
    "refresh_interval": {"type": (int, float), "min": 0.1, "max": 3600},
    "auto_start": {"type": bool},
    "confirm_quit": {"type": bool},
    "animations_enabled": {"type": bool},
    "github_refresh_interval": {"type": (int, float), "min": 15, "max": 3600},
    "_schema_version": {"type": int},
    "_created": {"type": (str, type(None))},
    "_modified": {"type": (str, type(None))},
}


class ConfigManager:
    """Load, save, and query application configuration stored as JSON.

    The manager is **thread-safe** — concurrent ``get`` / ``set`` / ``save``
    calls are serialised through an ``RLock``.
    """

    def __init__(self, config_dir: Path | None = None) -> None:
        self._dir = config_dir or CONFIG_DIR
        self._path = self._dir / CONFIG_FILENAME
        self._backup_dir = self._dir / "backups"
        self._data: dict[str, Any] = dict(_DEFAULT_CONFIG)
        self._lock = threading.RLock()

    # ── Properties ──────────────────────────────────────

    @property
    def path(self) -> Path:
        """Return the path to the configuration file."""
        return self._path

    # ── Public API ──────────────────────────────────────

    def load(self) -> None:
        """Load configuration from disk, creating the directory if needed."""
        with self._lock:
            self._ensure_dir()
            if not self._path.exists():
                log.info("No config file found - writing defaults to %s", self._path)
                self._write()
                return
            try:
                raw = self._path.read_text(encoding="utf-8")
                stored = json.loads(raw)
                if not isinstance(stored, dict):
                    raise TypeError("Config root must be a JSON object")
                # Merge stored values on top of defaults so new keys are always present.
                self._data = {**_DEFAULT_CONFIG, **stored}

                # Run migration if needed
                self.migrate()

                # Validate loaded config
                errors = self.validate()
                if errors:
                    log.warning("Config validation errors: %s", errors)
                    # Create backup of invalid config
                    self._create_backup("invalid_config")

                log.debug("Loaded config: %s", self._data)
            except (json.JSONDecodeError, TypeError) as exc:
                log.warning("Corrupt config - resetting to defaults: %s", exc)
                # Create backup of corrupt config
                if self._path.exists():
                    self._create_backup("corrupt_config")
                self._data = dict(_DEFAULT_CONFIG)
                self._write()

    def save(self) -> None:
        """Persist current configuration to disk."""
        with self._lock:
            self._ensure_dir()
            self._write()

    def get(self, key: str, default: Any = None) -> Any:
        """Return a configuration value (thread-safe)."""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value and persist immediately."""
        with self._lock:
            self._data[key] = value
            self._write()
            log.debug("Config updated: %s = %r", key, value)

    def as_dict(self) -> dict[str, Any]:
        """Return a snapshot copy of the current configuration."""
        with self._lock:
            return dict(self._data)

    # ── Enhanced Configuration Management ───────────────

    def validate(self) -> list[str]:
        """Validate configuration against schema.

        Returns:
            List of validation error messages, empty if valid.
        """
        errors = []
        with self._lock:
            for key, value in self._data.items():
                if key not in _CONFIG_SCHEMA:
                    errors.append(f"Unknown config key: {key}")
                    continue

                schema = _CONFIG_SCHEMA[key]
                expected_type = schema.get("type")

                # Type check
                if expected_type and not isinstance(value, expected_type):
                    errors.append(f"Key '{key}': expected {expected_type}, got {type(value)}")
                    continue

                # Allowed values check
                if "allowed" in schema and value not in schema["allowed"]:
                    errors.append(f"Key '{key}': value '{value}' not in {schema['allowed']}")

                # Range check for numbers
                if isinstance(value, (int, float)):
                    if "min" in schema and value < schema["min"]:
                        errors.append(f"Key '{key}': value {value} < minimum {schema['min']}")
                    if "max" in schema and value > schema["max"]:
                        errors.append(f"Key '{key}': value {value} > maximum {schema['max']}")

        return errors

    def migrate(self) -> bool:
        """Migrate configuration to current schema version.

        Returns:
            True if migration was performed, False otherwise.
        """
        with self._lock:
            current_version = self._data.get("_schema_version", 0)

            if current_version == CONFIG_SCHEMA_VERSION:
                return False

            log.info(
                "Migrating config from version %s to %s",
                current_version,
                CONFIG_SCHEMA_VERSION,
            )

            # Migration logic for future versions
            # For now, just update the version
            self._data["_schema_version"] = CONFIG_SCHEMA_VERSION

            # Update timestamps
            self._update_timestamps()

            self._write()
            return True

    def export(self, export_path: Path) -> bool:
        """Export configuration to a file.

        Args:
            export_path: Path to export configuration to.

        Returns:
            True if export succeeded, False otherwise.
        """
        try:
            with self._lock:
                export_data = dict(self._data)
                # Remove internal metadata for export
                export_data.pop("_schema_version", None)
                export_data.pop("_created", None)
                export_data.pop("_modified", None)

                export_path.write_text(
                    json.dumps(export_data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                log.info("Configuration exported to %s", export_path)
                return True
        except Exception as e:
            log.error("Failed to export configuration: %s", e)
            return False

    def import_config(self, import_path: Path) -> bool:
        """Import configuration from a file.

        Args:
            import_path: Path to import configuration from.

        Returns:
            True if import succeeded, False otherwise.
        """
        try:
            # Create backup before import
            self._create_backup("pre_import")

            with self._lock:
                raw = import_path.read_text(encoding="utf-8")
                imported = json.loads(raw)

                if not isinstance(imported, dict):
                    raise TypeError("Imported config must be a JSON object")

                # Validate imported data
                temp_data = {**_DEFAULT_CONFIG, **imported}
                temp_manager = ConfigManager()
                temp_manager._data = temp_data
                errors = temp_manager.validate()

                if errors:
                    log.error("Imported config validation failed: %s", errors)
                    return False

                # Import successful, update data
                self._data.update(imported)
                self._data["_schema_version"] = CONFIG_SCHEMA_VERSION
                self._update_timestamps()

                self._write()
                log.info("Configuration imported from %s", import_path)
                return True

        except Exception as e:
            log.error("Failed to import configuration: %s", e)
            return False

    def reset_to_defaults(self) -> bool:
        """Reset configuration to defaults.

        Returns:
            True if reset succeeded, False otherwise.
        """
        try:
            # Create backup before reset
            self._create_backup("pre_reset")

            with self._lock:
                self._data = dict(_DEFAULT_CONFIG)
                self._update_timestamps()
                self._write()
                log.info("Configuration reset to defaults")
                return True
        except Exception as e:
            log.error("Failed to reset configuration: %s", e)
            return False

    def create_backup(self, reason: str = "manual") -> bool:
        """Create a backup of the current configuration.

        Args:
            reason: Reason for backup (used in filename).

        Returns:
            True if backup succeeded, False otherwise.
        """
        return self._create_backup(reason)

    # ── Internals ───────────────────────────────────────

    def _ensure_dir(self) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)

    def _ensure_backup_dir(self) -> None:
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _update_timestamps(self) -> None:
        """Update creation and modification timestamps."""
        now = datetime.now().isoformat()

        if "_created" not in self._data or self._data["_created"] is None:
            self._data["_created"] = now

        self._data["_modified"] = now

    def _create_backup(self, reason: str) -> bool:
        """Create a backup of the current configuration file."""
        try:
            self._ensure_backup_dir()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"config_backup_{timestamp}_{reason}.json"
            backup_path = self._backup_dir / backup_name

            if self._path.exists():
                shutil.copy2(self._path, backup_path)
                log.debug("Configuration backed up to %s", backup_path)

            # Clean up old backups (keep last 10)
            self._cleanup_old_backups()

            return True
        except Exception as e:
            log.error("Failed to create backup: %s", e)
            return False

    def _cleanup_old_backups(self, keep_count: int = 10) -> None:
        """Clean up old backup files, keeping only the most recent ones."""
        try:
            if not self._backup_dir.exists():
                return

            backups = list(self._backup_dir.glob("config_backup_*.json"))
            backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            for backup in backups[keep_count:]:
                backup.unlink()
                log.debug("Removed old backup: %s", backup.name)
        except Exception as e:
            log.error("Failed to cleanup old backups: %s", e)

    def _write(self) -> None:
        """Write configuration to disk with metadata."""
        self._update_timestamps()
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
