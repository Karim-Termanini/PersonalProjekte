"""HypeDevHome — Development Folder Creator.

Handles creation of the development directory with optional Btrfs subvolume
optimization and proper permissions.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class DevFolderResult:
    """Result of dev folder creation operation."""

    success: bool
    path: str
    btrfs_optimized: bool = False
    permissions: str = ""
    message: str = ""
    suggestions: list[str] = field(default_factory=list)


class DevFolderCreator:
    """Manages development directory creation with filesystem optimizations."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor

    async def create_dev_folder(
        self,
        path: str = "~/Dev",
        use_btrfs: bool = False,
        permissions: int = 0o755,
    ) -> DevFolderResult:
        """Create the main development folder with optional Btrfs optimization.

        Args:
            path: Target directory path (supports ~ expansion).
            use_btrfs: If True, attempt Btrfs subvolume creation.
            permissions: Unix permissions mode (default: 0o755).

        Returns:
            DevFolderResult with outcome and suggestions.
        """
        expanded_path = os.path.expanduser(path)
        log.info("Creating dev folder at: %s", expanded_path)

        # Check if path already exists
        check_result = await self._executor.run_async(["test", "-e", expanded_path])
        if check_result.success:
            # Check if it's a directory
            is_dir = await self._executor.run_async(["test", "-d", expanded_path])
            if not is_dir.success:
                return DevFolderResult(
                    success=False,
                    path=expanded_path,
                    message=f"Path exists but is not a directory: {expanded_path}",
                )

            # Already exists as directory - verify permissions
            return await self._verify_existing(expanded_path, permissions)

        # Directory doesn't exist - create it
        if use_btrfs:
            btrfs_result = await self._try_btrfs_subvolume(expanded_path, permissions)
            if btrfs_result:
                return btrfs_result

        # Fallback: standard mkdir
        log.info("Creating directory with mkdir -p")
        mkdir_result = await self._executor.run_async(["mkdir", "-p", expanded_path])
        if not mkdir_result.success:
            return DevFolderResult(
                success=False,
                path=expanded_path,
                message=f"Failed to create directory: {mkdir_result.stderr}",
            )

        # Set permissions
        chmod_result = await self._executor.run_async(["chmod", oct(permissions), expanded_path])
        if not chmod_result.success:
            log.warning("Failed to set permissions: %s", chmod_result.stderr)

        return DevFolderResult(
            success=True,
            path=expanded_path,
            permissions=oct(permissions),
            message="Development folder created successfully",
        )

    async def _verify_existing(self, path: str, expected_permissions: int) -> DevFolderResult:
        """Verify existing directory and suggest improvements."""
        suggestions = []

        # Check filesystem type
        fs_type = await self._executor.get_fs_type(path)
        if fs_type == "btrfs":
            # Check if it's a subvolume
            subvolume_check = await self._executor.run_async(
                ["btrfs", "subvolume", "show", path], root=True
            )
            if not subvolume_check.success:
                suggestions.append(
                    "Directory is on Btrfs but not a subvolume. "
                    "Consider converting for better performance."
                )

        # Check mount options for noatime, discard
        if fs_type:
            mount_check = await self._executor.run_async(["findmnt", "-n", "-o", "OPTIONS", path])
            if mount_check.success:
                options = mount_check.stdout.strip()
                if "noatime" not in options:
                    suggestions.append(
                        "Consider adding 'noatime' mount option for better I/O performance."
                    )
                if "discard" not in options and fs_type in ("btrfs", "ext4"):
                    suggestions.append(
                        f"Consider adding 'discard' mount option for {fs_type.upper()} filesystem."
                    )

        return DevFolderResult(
            success=True,
            path=path,
            permissions=oct(expected_permissions),
            message="Development folder already exists",
            suggestions=suggestions,
        )

    async def _try_btrfs_subvolume(self, path: str, permissions: int) -> DevFolderResult | None:
        """Attempt to create Btrfs subvolume. Returns None if not applicable."""
        parent = os.path.dirname(path)

        # Check if parent is on Btrfs
        fs_type = await self._executor.get_fs_type(parent)
        if fs_type != "btrfs":
            log.info("Parent directory not on Btrfs, skipping subvolume creation")
            return None

        log.info("Btrfs detected, creating subvolume: %s", path)

        # Create parent directories first
        mkdir_parent = await self._executor.run_async(["mkdir", "-p", parent])
        if not mkdir_parent.success:
            return DevFolderResult(
                success=False,
                path=path,
                message=f"Failed to create parent directory: {mkdir_parent.stderr}",
            )

        # Create Btrfs subvolume (requires root)
        result = await self._executor.run_async(["btrfs", "subvolume", "create", path], root=True)

        if result.success:
            log.info("Btrfs subvolume created successfully: %s", path)

            # Set permissions on subvolume
            chmod_result = await self._executor.run_async(["chmod", oct(permissions), path])
            if not chmod_result.success:
                log.warning("Failed to set permissions on Btrfs subvolume")

            return DevFolderResult(
                success=True,
                path=path,
                btrfs_optimized=True,
                permissions=oct(permissions),
                message="Btrfs subvolume created successfully",
                suggestions=[
                    "Btrfs subvolume created with snapshot capabilities.",
                    "You can now use 'btrfs subvolume snapshot' for quick backups.",
                ],
            )

        # Btrfs subvolume creation failed - fallback to mkdir
        log.warning(
            "Btrfs subvolume creation failed: %s. Falling back to standard mkdir.",
            result.stderr,
        )
        return None

    async def create_nested_folders(self, base_path: str) -> bool:
        """Create common nested development folders.

        Creates: projects, experiments, tools, docs
        """
        expanded_path = os.path.expanduser(base_path)
        nested = ["projects", "experiments", "tools", "docs"]

        success = True
        for folder in nested:
            full_path = os.path.join(expanded_path, folder)
            result = await self._executor.run_async(["mkdir", "-p", full_path])
            if not result.success:
                log.warning("Failed to create nested folder: %s", folder)
                success = False

        return success

    async def delete_folder(self, path: str, force: bool = False) -> bool:
        """Delete the development folder (with safety checks).

        Args:
            path: Directory to delete.
            force: If True, skip safety prompts.

        Returns:
            True if deletion succeeded.
        """
        expanded_path = os.path.expanduser(path)

        # Safety check: only delete if path contains "Dev" or "dev"
        if not force and "dev" not in expanded_path.lower():
            log.error(
                "Refusing to delete non-dev folder: %s. Use force=True to override.",
                expanded_path,
            )
            return False

        result = await self._executor.run_async(["rm", "-rf", expanded_path])
        return result.success
