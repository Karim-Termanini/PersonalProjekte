"""HypeDevHome — Pluggable Snapshot Storage System (Guardian Layer).

Provides an abstract interface and a local filesystem implementation for storing
and retrieving isolated development environment snapshots. Supporting async I/O
and detailed metadata tracking.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ─── Enums & Models ──────────────────────────────────────────────────


class SnapshotType(Enum):
    """Types of snapshots supported."""

    CONTAINER = auto()
    DOTFILES = auto()
    CONFIG = auto()
    SYSTEM_HOSTS = auto()
    FULL_ENVIRONMENT = auto()


@dataclass
class SnapshotMetadata:
    """Metadata for a single snapshot."""

    snapshot_id: str
    name: str
    snapshot_type: SnapshotType
    timestamp: str
    container_name: str | None = None
    encrypted: bool = False
    sha256_checksum: str = ""
    size_bytes: int = 0
    stack_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_healthy(self) -> bool:
        """Check if snapshot has valid checksum."""
        return bool(self.sha256_checksum)


# ─── Storage Providers ──────────────────────────────────────────────


class SnapshotStorageProvider(ABC):
    """Abstract base class for pluggable snapshot storage."""

    @abstractmethod
    async def save(self, snapshot_id: str, data: bytes, metadata: SnapshotMetadata) -> bool:
        """Save raw snapshot data to storage."""
        pass

    @abstractmethod
    async def load(self, snapshot_id: str) -> tuple[bytes, SnapshotMetadata] | None:
        """Load raw snapshot data and metadata from storage."""
        pass

    @abstractmethod
    async def list_snapshots(self, stack_name: str | None = None) -> list[SnapshotMetadata]:
        """List available snapshots across all stacks or a specific stack."""
        pass

    @abstractmethod
    async def delete(self, snapshot_id: str) -> bool:
        """Permanently remove a snapshot from storage."""
        pass

    @abstractmethod
    async def get_disk_usage(self) -> int:
        """Get total bytes used by all snapshots in storage."""
        pass


class LocalStorageProvider(SnapshotStorageProvider):
    """Local filesystem implementation of SnapshotStorageProvider."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        if base_dir:
            self._base_dir = Path(base_dir).expanduser()
        else:
            xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            self._base_dir = Path(xdg_data) / "hypedevhome" / "snapshots"

        self._base_dir.mkdir(parents=True, exist_ok=True)
        log.info("LocalStorageProvider initialized at %s", self._base_dir)

    async def save(self, snapshot_id: str, data: bytes, metadata: SnapshotMetadata) -> bool:
        try:
            stack_dir = self._base_dir / (metadata.stack_name or "default")
            stack_dir.mkdir(parents=True, exist_ok=True)

            data_path = stack_dir / f"{snapshot_id}.tar.gz"
            data_path.write_bytes(data)

            meta_path = stack_dir / f"{snapshot_id}.json"
            meta_path.write_text(
                json.dumps(
                    {
                        "snapshot_id": metadata.snapshot_id,
                        "name": metadata.name,
                        "snapshot_type": metadata.snapshot_type.name,
                        "timestamp": metadata.timestamp,
                        "container_name": metadata.container_name,
                        "encrypted": metadata.encrypted,
                        "sha256_checksum": metadata.sha256_checksum,
                        "size_bytes": metadata.size_bytes,
                        "stack_name": metadata.stack_name,
                        "metadata": metadata.metadata,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            log.error("Failed to save snapshot to local storage: %s", e)
            return False

    async def load(self, snapshot_id: str) -> tuple[bytes, SnapshotMetadata] | None:
        try:
            # Search across all stack subdirectories
            for stack_dir in self._base_dir.iterdir():
                if not stack_dir.is_dir():
                    continue

                data_path = stack_dir / f"{snapshot_id}.tar.gz"
                meta_path = stack_dir / f"{snapshot_id}.json"

                if data_path.exists() and meta_path.exists():
                    data = data_path.read_bytes()
                    meta_dict = json.loads(meta_path.read_text(encoding="utf-8"))

                    metadata = SnapshotMetadata(
                        snapshot_id=meta_dict["snapshot_id"],
                        name=meta_dict["name"],
                        snapshot_type=SnapshotType[meta_dict["snapshot_type"]],
                        timestamp=meta_dict["timestamp"],
                        container_name=meta_dict.get("container_name"),
                        encrypted=meta_dict.get("encrypted", False),
                        sha256_checksum=meta_dict.get("sha256_checksum", ""),
                        size_bytes=meta_dict.get("size_bytes", 0),
                        stack_name=meta_dict.get("stack_name"),
                        metadata=meta_dict.get("metadata", {}),
                    )
                    return data, metadata
            return None
        except Exception as e:
            log.error("Failed to load snapshot from local storage: %s", e)
            return None

    async def list_snapshots(self, stack_name: str | None = None) -> list[SnapshotMetadata]:
        snapshots = []
        try:
            search_dirs = [self._base_dir / stack_name] if stack_name else self._base_dir.iterdir()

            for entry in search_dirs:
                if not isinstance(entry, Path) or not entry.is_dir():
                    continue

                for meta_file in entry.glob("*.json"):
                    try:
                        meta_dict = json.loads(meta_file.read_text(encoding="utf-8"))
                        snapshots.append(
                            SnapshotMetadata(
                                snapshot_id=meta_dict["snapshot_id"],
                                name=meta_dict["name"],
                                snapshot_type=SnapshotType[meta_dict["snapshot_type"]],
                                timestamp=meta_dict["timestamp"],
                                container_name=meta_dict.get("container_name"),
                                encrypted=meta_dict.get("encrypted", False),
                                sha256_checksum=meta_dict.get("sha256_checksum", ""),
                                size_bytes=meta_dict.get("size_bytes", 0),
                                stack_name=meta_dict.get("stack_name"),
                                metadata=meta_dict.get("metadata", {}),
                            )
                        )
                    except Exception as e:
                        log.warning("Skipping malformed snapshot metadata %s: %s", meta_file, e)
            return snapshots
        except Exception as e:
            log.error("Failed to list snapshots: %s", e)
            return []

    async def delete(self, snapshot_id: str) -> bool:
        try:
            for stack_dir in self._base_dir.iterdir():
                if not stack_dir.is_dir():
                    continue

                data_path = stack_dir / f"{snapshot_id}.tar.gz"
                meta_path = stack_dir / f"{snapshot_id}.json"

                if data_path.exists():
                    data_path.unlink()
                if meta_path.exists():
                    meta_path.unlink()
                    return True
            return False
        except Exception as e:
            log.error("Failed to delete snapshot %s: %s", snapshot_id, e)
            return False

    async def get_disk_usage(self) -> int:
        total = 0
        try:
            for root, _, files in os.walk(self._base_dir):
                for f in files:
                    total += os.path.getsize(os.path.join(root, f))
            return total
        except Exception as e:
            log.error("Failed to calculate disk usage: %s", e)
            return 0
