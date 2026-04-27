"""HypeDevHome — Configuration Backup & Restore System.

Provides automatic backup of user configurations before applying changes,
with support for backup history, restore, export/import, and change preview.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class BackupMetadata:
    """Metadata for a backup archive."""

    timestamp: str
    backup_id: str
    files: list[str]
    description: str = ""
    success: bool = True
    error: str = ""


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    backup_path: str = ""
    metadata: BackupMetadata | None = None
    message: str = ""


@dataclass
class RestoreResult:
    """Result of a restore operation."""

    success: bool
    restored_files: list[str] = field(default_factory=list)
    failed_files: list[str] = field(default_factory=list)
    message: str = ""


class ConfigBackupManager:
    """Manages backup and restore of configuration files."""

    # Configuration files to backup
    CONFIG_FILES: ClassVar[dict[str, list[str]]] = {
        "git": ["~/.gitconfig", "~/.gitignore_global"],
        "shell": [
            "~/.bashrc",
            "~/.zshrc",
            "~/.profile",
            "~/.bash_profile",
            "~/.config/fish/config.fish",
        ],
        "ssh": ["~/.ssh/config", "~/.ssh-agent-info"],
        "editor": [
            "~/.config/nvim/init.vim",
            "~/.config/nvim/init.lua",
            "~/.vimrc",
            "~/.config/Code/User/settings.json",
        ],
        "file_manager": [
            "~/.config/nautilus/preferences",
            "~/.config/dolphinrc",
            "~/.config/nemo/preferences",
        ],
    }

    def __init__(self, executor: HostExecutor, backup_dir: str = "~/.hypedevhome/backups") -> None:
        self._executor = executor
        self._backup_dir = os.path.expanduser(backup_dir)

    async def create_backup(self, description: str = "") -> BackupResult:
        """Create a timestamped backup of all configuration files.

        Args:
            description: Optional description for this backup.

        Returns:
            BackupResult with backup path and metadata.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"backup_{timestamp}"
        backup_path = os.path.join(self._backup_dir, backup_id)

        log.info("Creating backup: %s", backup_id)

        # Create backup directory
        mkdir_result = await self._executor.run_async(["mkdir", "-p", backup_path])
        if not mkdir_result.success:
            return BackupResult(
                success=False,
                message=f"Failed to create backup directory: {mkdir_result.stderr}",
            )

        # Collect all files that exist
        files_to_backup = []
        backed_up_files = []

        for category, file_list in self.CONFIG_FILES.items():
            for file_path in file_list:
                expanded_path = os.path.expanduser(file_path)
                if await self._file_exists(expanded_path):
                    files_to_backup.append((category, expanded_path))

        # Backup each file
        for category, file_path in files_to_backup:
            category_dir = os.path.join(backup_path, category)
            mkdir_cat = await self._executor.run_async(["mkdir", "-p", category_dir])
            if not mkdir_cat.success:
                continue

            # Preserve directory structure
            dest_path = os.path.join(category_dir, os.path.basename(file_path))

            copy_result = await self._executor.run_async(["cp", "-a", file_path, dest_path])
            if copy_result.success:
                backed_up_files.append(file_path)
                log.debug("Backed up: %s -> %s", file_path, dest_path)
            else:
                log.warning("Failed to backup: %s", file_path)

        # Create metadata
        metadata = BackupMetadata(
            timestamp=timestamp,
            backup_id=backup_id,
            files=backed_up_files,
            description=description,
        )

        # Save metadata as JSON
        metadata_path = os.path.join(backup_path, "metadata.json")
        await self._save_metadata(metadata_path, metadata)

        success = len(backed_up_files) > 0
        return BackupResult(
            success=success,
            backup_path=backup_path,
            metadata=metadata,
            message=f"Backup created: {len(backed_up_files)} files"
            if success
            else "No files to backup",
        )

    async def restore_backup(self, backup_id: str) -> RestoreResult:
        """Restore configuration files from a specific backup.

        Args:
            backup_id: ID of the backup to restore (e.g., "backup_20260414_123456").

        Returns:
            RestoreResult with restored/failed files.
        """
        backup_path = os.path.join(self._backup_dir, backup_id)

        # Check if backup exists
        if not await self._file_exists(backup_path):
            return RestoreResult(
                success=False,
                message=f"Backup not found: {backup_id}",
            )

        log.info("Restoring from backup: %s", backup_id)

        # Load metadata
        metadata_path = os.path.join(backup_path, "metadata.json")
        metadata = await self._load_metadata(metadata_path)
        if not metadata:
            return RestoreResult(
                success=False,
                message="Failed to load backup metadata",
            )

        restored_files = []
        failed_files = []

        # Restore each file
        for category, file_list in self.CONFIG_FILES.items():
            for original_path in file_list:
                expanded_original = os.path.expanduser(original_path)
                backup_file = os.path.join(
                    backup_path, category, os.path.basename(expanded_original)
                )

                if not await self._file_exists(backup_file):
                    continue

                # Create backup of current file before restore
                if await self._file_exists(expanded_original):
                    pre_restore_backup = f"{expanded_original}.pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    await self._executor.run_async(
                        ["cp", "-a", expanded_original, pre_restore_backup]
                    )

                # Restore from backup
                # Ensure parent directory exists
                parent_dir = os.path.dirname(expanded_original)
                await self._executor.run_async(["mkdir", "-p", parent_dir])

                restore_result = await self._executor.run_async(
                    ["cp", "-a", backup_file, expanded_original]
                )
                if restore_result.success:
                    restored_files.append(expanded_original)
                    log.debug("Restored: %s", expanded_original)
                else:
                    failed_files.append(expanded_original)
                    log.warning("Failed to restore: %s", expanded_original)

        success = len(restored_files) > 0 and len(failed_files) == 0
        return RestoreResult(
            success=success,
            restored_files=restored_files,
            failed_files=failed_files,
            message=f"Restored {len(restored_files)} files, {len(failed_files)} failed",
        )

    async def list_backups(self) -> list[BackupMetadata]:
        """List all available backups with metadata.

        Returns:
            List of BackupMetadata objects, sorted by timestamp (newest first).
        """
        backups: list[BackupMetadata] = []

        # Check if backup directory exists
        if not await self._file_exists(self._backup_dir):
            return backups

        # List all subdirectories
        result = await self._executor.run_async(
            ["find", self._backup_dir, "-mindepth", "1", "-maxdepth", "1", "-type", "-d"]
        )
        if not result.success:
            return backups

        backup_dirs = result.stdout.strip().splitlines()

        for backup_dir in backup_dirs:
            metadata_path = os.path.join(backup_dir, "metadata.json")
            metadata = await self._load_metadata(metadata_path)
            if metadata:
                backups.append(metadata)

        # Sort by timestamp (newest first)
        backups.sort(key=lambda m: m.timestamp, reverse=True)
        return backups

    async def get_latest_backup(self) -> BackupMetadata | None:
        """Get the most recent backup.

        Returns:
            BackupMetadata of the latest backup, or None if no backups exist.
        """
        backups = await self.list_backups()
        return backups[0] if backups else None

    async def delete_backup(self, backup_id: str) -> bool:
        """Delete a specific backup.

        Args:
            backup_id: ID of the backup to delete.

        Returns:
            True if deletion succeeded.
        """
        backup_path = os.path.join(self._backup_dir, backup_id)

        if not await self._file_exists(backup_path):
            return False

        result = await self._executor.run_async(["rm", "-rf", backup_path])
        return result.success

    async def export_backup(self, backup_id: str, dest_path: str) -> bool:
        """Export a backup as a tar.gz archive.

        Args:
            backup_id: ID of the backup to export.
            dest_path: Destination path for the archive.

        Returns:
            True if export succeeded.
        """
        backup_path = os.path.join(self._backup_dir, backup_id)

        if not await self._file_exists(backup_path):
            return False

        expanded_dest = os.path.expanduser(dest_path)
        result = await self._executor.run_async(
            ["tar", "-czf", expanded_dest, "-C", self._backup_dir, backup_id]
        )
        return result.success

    async def import_backup(self, archive_path: str) -> BackupResult:
        """Import a backup from a tar.gz archive.

        Args:
            archive_path: Path to the archive file.

        Returns:
            BackupResult with imported backup info.
        """
        expanded_archive = os.path.expanduser(archive_path)

        if not await self._file_exists(expanded_archive):
            return BackupResult(
                success=False,
                message=f"Archive not found: {archive_path}",
            )

        # Create backup directory if needed
        mkdir_result = await self._executor.run_async(["mkdir", "-p", self._backup_dir])
        if not mkdir_result.success:
            return BackupResult(
                success=False,
                message="Failed to create backup directory",
            )

        # Extract archive
        result = await self._executor.run_async(
            ["tar", "-xzf", expanded_archive, "-C", self._backup_dir]
        )
        if not result.success:
            return BackupResult(
                success=False,
                message=f"Failed to extract archive: {result.stderr}",
            )

        # Read metadata from extracted backup
        archive_name = os.path.basename(expanded_archive).replace(".tar.gz", "")
        metadata_path = os.path.join(self._backup_dir, archive_name, "metadata.json")
        metadata = await self._load_metadata(metadata_path)

        return BackupResult(
            success=True,
            backup_path=os.path.join(self._backup_dir, archive_name),
            metadata=metadata,
            message=f"Imported backup: {archive_name}",
        )

    async def preview_changes(self, backup_id: str) -> dict[str, dict[str, Any]]:
        """Preview what changes will be applied during restore.

        Args:
            backup_id: ID of the backup to preview.

        Returns:
            Dict mapping file paths to {"backup": ..., "current": ...} info.
        """
        backup_path = os.path.join(self._backup_dir, backup_id)
        preview: dict[str, dict[str, Any]] = {}

        if not await self._file_exists(backup_path):
            return preview

        for category, file_list in self.CONFIG_FILES.items():
            for original_path in file_list:
                expanded_original = os.path.expanduser(original_path)
                backup_file = os.path.join(
                    backup_path, category, os.path.basename(expanded_original)
                )

                if not await self._file_exists(backup_file):
                    continue

                # Get file info
                backup_info = await self._get_file_info(backup_file)
                current_info = (
                    await self._get_file_info(expanded_original)
                    if await self._file_exists(expanded_original)
                    else None
                )

                preview[expanded_original] = {
                    "backup": backup_info,
                    "current": current_info,
                }

        return preview

    async def _file_exists(self, path: str) -> bool:
        """Check if a file exists on the host."""
        result = await self._executor.run_async(["test", "-e", path])
        return result.success

    async def _get_file_info(self, path: str) -> dict[str, str]:
        """Get file information (size, modification time)."""
        info = {}

        # Get file size
        size_result = await self._executor.run_async(["stat", "-c", "%s", path])
        if size_result.success:
            info["size"] = size_result.stdout.strip()

        # Get modification time
        mtime_result = await self._executor.run_async(["stat", "-c", "%Y", path])
        if mtime_result.success:
            info["modified"] = mtime_result.stdout.strip()

        return info

    async def _save_metadata(self, path: str, metadata: BackupMetadata) -> None:
        """Save backup metadata as JSON."""
        try:
            with open(path, "w") as f:
                json.dump(
                    {
                        "timestamp": metadata.timestamp,
                        "backup_id": metadata.backup_id,
                        "files": metadata.files,
                        "description": metadata.description,
                        "success": metadata.success,
                        "error": metadata.error,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            log.error("Failed to save metadata: %s", e)

    async def _load_metadata(self, path: str) -> BackupMetadata | None:
        """Load backup metadata from JSON."""
        if not await self._file_exists(path):
            return None

        try:
            # Read file content via executor (for host files)
            result = await self._executor.run_async(["cat", path])
            if not result.success:
                return None

            data = json.loads(result.stdout)
            return BackupMetadata(
                timestamp=data.get("timestamp", ""),
                backup_id=data.get("backup_id", ""),
                files=data.get("files", []),
                description=data.get("description", ""),
                success=data.get("success", True),
                error=data.get("error", ""),
            )
        except (json.JSONDecodeError, Exception) as e:
            log.error("Failed to load metadata: %s", e)
            return None

    async def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """Remove old backups, keeping only the most recent ones.

        Args:
            keep_count: Number of recent backups to keep.

        Returns:
            Number of backups deleted.
        """
        backups = await self.list_backups()
        deleted = 0

        if len(backups) <= keep_count:
            return 0

        # Delete oldest backups
        for backup in backups[keep_count:]:
            if await self.delete_backup(backup.backup_id):
                deleted += 1

        return deleted
