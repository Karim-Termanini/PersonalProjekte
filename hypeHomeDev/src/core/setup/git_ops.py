"""HypeDevHome — Git Operations Service.

Advanced git operations with progress tracking and error handling.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

from core.setup.models import RepoInfo

log = logging.getLogger(__name__)


def canonical_git_remote(url: str) -> str:
    """Normalize git remote URLs for loose equality (HTTPS vs git@, optional .git)."""
    u = url.strip()
    if not u:
        return ""
    if u.endswith(".git"):
        u = u[:-4]
    u = u.lower()
    if u.startswith("git@"):
        rest = u[4:]
        if ":" in rest:
            host, path = rest.split(":", 1)
            return f"{host}/{path.lstrip('/')}"
        return rest
    if u.startswith(("https://", "http://", "ssh://", "git://")):
        p = urlparse(u)
        if p.netloc and p.path:
            return f"{p.netloc}{p.path}".rstrip("/").replace("//", "/")
    return u


def remotes_equivalent(existing: str | None, requested: str) -> bool:
    """Return True if two remotes likely refer to the same repository."""
    if not existing or not requested:
        return False
    return canonical_git_remote(existing) == canonical_git_remote(requested)


@dataclass
class GitRepoInfo:
    """Information about a git repository."""

    url: str
    local_path: str
    branch: str = "main"
    exists: bool = False
    is_git_repo: bool = False
    current_branch: str | None = None
    remote_url: str | None = None
    status: str = "unknown"


class GitOperations:
    """Advanced git operations with progress tracking."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor

    async def clone(
        self,
        url: str,
        target_path: str,
        branch: str = "main",
        depth: int = 1,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Clone a git repository with progress tracking."""
        target_path = os.path.expanduser(target_path)
        try:
            # Validate URL
            if not await self._validate_git_url(url):
                log.error("Invalid git URL: %s", url)
                if progress_callback:
                    progress_callback("Invalid git URL", 0.0)
                return False

            # Check if directory exists
            repo_info = await self.get_repo_info(target_path)
            if repo_info.exists:
                if repo_info.is_git_repo:
                    log.info("Repository already exists at %s", target_path)
                    if progress_callback:
                        progress_callback("Repository already exists", 1.0)
                    return True
                else:
                    log.warning("Directory exists but is not a git repo: %s", target_path)
                    if progress_callback:
                        progress_callback("Directory exists but is not a git repo", 0.0)
                    return False

            # Create parent directory
            parent_dir = os.path.dirname(target_path)
            if parent_dir and parent_dir != ".":
                await self._executor.run_async(["mkdir", "-p", parent_dir])

            # Build git command
            cmd = ["git", "clone"]
            if depth:
                cmd.extend(["--depth", str(depth)])
            if branch and branch != "main":
                cmd.extend(["-b", branch])
            cmd.extend([url, target_path])

            if progress_callback:
                progress_callback(f"Cloning {url}...", 0.1)

            # Execute clone
            result = await self._executor.run_async(cmd)

            if result.success:
                log.info("Successfully cloned %s to %s", url, target_path)
                if progress_callback:
                    progress_callback(f"Cloned {url}", 1.0)
                return True
            else:
                log.error("Failed to clone %s: %s", url, result.stderr)
                if progress_callback:
                    progress_callback(f"Failed to clone: {result.stderr[:100]}", 0.0)
                return False

        except Exception as e:
            log.exception("Error cloning repository: %s", e)
            if progress_callback:
                progress_callback(f"Error: {str(e)[:100]}", 0.0)
            return False

    async def pull(
        self,
        repo_path: str,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Pull latest changes from remote."""
        repo_path = os.path.expanduser(repo_path)
        try:
            repo_info = await self.get_repo_info(repo_path)
            if not repo_info.is_git_repo:
                log.error("Not a git repository: %s", repo_path)
                return False

            if progress_callback:
                progress_callback("Pulling latest changes...", 0.1)

            # Change to repo directory and pull
            cmd = ["git", "-C", repo_path, "pull", "--rebase"]
            result = await self._executor.run_async(cmd)

            if result.success:
                log.info("Successfully pulled latest changes for %s", repo_path)
                if progress_callback:
                    progress_callback("Pulled latest changes", 1.0)
                return True
            else:
                log.error("Failed to pull %s: %s", repo_path, result.stderr)
                if progress_callback:
                    progress_callback(f"Pull failed: {result.stderr[:100]}", 0.0)
                return False

        except Exception as e:
            log.exception("Error pulling repository: %s", e)
            return False

    async def clone_or_update(
        self,
        url: str,
        target_path: str,
        branch: str = "main",
        depth: int = 1,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Clone into ``target_path`` or, if a matching repo already exists, ``git pull``.

        Remote URLs are compared with :func:`remotes_equivalent` so HTTPS and SSH
        forms of the same GitHub/GitLab repo match. If the directory exists as a
        non-git folder, or as a git repo with a different ``origin``, returns False.
        """
        target_path = os.path.expanduser(target_path)
        try:
            if not await self._validate_git_url(url):
                log.error("Invalid git URL: %s", url)
                if progress_callback:
                    progress_callback("Invalid git URL", 0.0)
                return False

            repo_info = await self.get_repo_info(target_path)
            if repo_info.exists and repo_info.is_git_repo:
                if repo_info.remote_url and not remotes_equivalent(repo_info.remote_url, url):
                    msg = (
                        f"Path already exists with a different remote "
                        f"({repo_info.remote_url!r} vs {url!r})"
                    )
                    log.warning(msg)
                    if progress_callback:
                        progress_callback(msg, 0.0)
                    return False
                return await self.pull(target_path, progress_callback)

            return await self.clone(
                url,
                target_path,
                branch=branch,
                depth=depth,
                progress_callback=progress_callback,
            )

        except Exception as e:
            log.exception("Error in clone_or_update: %s", e)
            if progress_callback:
                progress_callback(f"Error: {str(e)[:100]}", 0.0)
            return False

    async def sync_repository(
        self,
        repo: RepoInfo,
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Clone or pull using fields from a :class:`~core.setup.models.RepoInfo`."""
        branch = repo.branch or "main"
        return await self.clone_or_update(
            url=repo.url,
            target_path=repo.target_path,
            branch=branch,
            progress_callback=progress_callback,
        )

    async def get_repo_info(self, path: str) -> GitRepoInfo:
        """Get information about a git repository."""
        path = os.path.expanduser(path)
        # Check if path exists
        check_dir = await self._executor.run_async(["test", "-d", path])
        exists = check_dir.success

        if not exists:
            return GitRepoInfo(url="", local_path=path, exists=False)

        # Check if it's a git repo
        check_git = await self._executor.run_async(["test", "-d", f"{path}/.git"])
        is_git_repo = check_git.success

        if not is_git_repo:
            return GitRepoInfo(url="", local_path=path, exists=True, is_git_repo=False)

        # Get git information
        info = GitRepoInfo(url="", local_path=path, exists=True, is_git_repo=True)

        # Get current branch
        branch_result = await self._executor.run_async(
            ["git", "-C", path, "branch", "--show-current"]
        )
        if branch_result.success:
            info.current_branch = branch_result.stdout.strip()

        # Get remote URL
        remote_result = await self._executor.run_async(
            ["git", "-C", path, "config", "--get", "remote.origin.url"]
        )
        if remote_result.success:
            info.remote_url = remote_result.stdout.strip()

        # Get status
        status_result = await self._executor.run_async(
            ["git", "-C", path, "status", "--porcelain"]
        )
        if status_result.success:
            if status_result.stdout.strip():
                info.status = "dirty"
            else:
                info.status = "clean"

        return info

    async def _validate_git_url(self, url: str) -> bool:
        """Validate a git URL."""
        # Basic URL validation
        if not url or not isinstance(url, str):
            return False

        # Check common git URL patterns
        patterns = [
            r"^https?://.+\.git$",
            r"^https?://.+$",
            r"^git@.+:.+\.git$",
            r"^git@.+:.+$",
            r"^ssh://git@.+:.+$",
            r"file:///.+$",
        ]

        return any(re.match(pattern, url) for pattern in patterns)

    async def setup_git_config(
        self,
        name: str | None = None,
        email: str | None = None,
        editor: str = "nvim",
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Setup git global configuration."""
        try:
            if progress_callback:
                progress_callback("Setting up git configuration...", 0.1)

            success = True

            # Set user name if provided
            if name:
                result = await self._executor.run_async(
                    ["git", "config", "--global", "user.name", name]
                )
                if not result.success:
                    log.error("Failed to set git user.name: %s", result.stderr)
                    success = False

            # Set user email if provided
            if email:
                result = await self._executor.run_async(
                    ["git", "config", "--global", "user.email", email]
                )
                if not result.success:
                    log.error("Failed to set git user.email: %s", result.stderr)
                    success = False

            # Set default editor
            result = await self._executor.run_async(
                ["git", "config", "--global", "core.editor", editor]
            )
            if not result.success:
                log.warning("Failed to set git editor: %s", result.stderr)

            # Set helpful defaults
            defaults = [
                ("pull.rebase", "true"),
                ("init.defaultBranch", "main"),
                ("color.ui", "auto"),
                ("credential.helper", "cache --timeout=3600"),
            ]

            for key, value in defaults:
                result = await self._executor.run_async(["git", "config", "--global", key, value])
                if not result.success:
                    log.warning("Failed to set git config %s: %s", key, result.stderr)

            if progress_callback:
                if success:
                    progress_callback("Git configuration complete", 1.0)
                else:
                    progress_callback("Git configuration partially failed", 0.5)

            return success

        except Exception as e:
            log.exception("Error setting up git config: %s", e)
            if progress_callback:
                progress_callback(f"Error: {str(e)[:100]}", 0.0)
            return False

    async def get_ssh_key_info(self) -> dict[str, str]:
        """Get information about SSH keys."""
        ssh_dir = "~/.ssh"
        result = await self._executor.run_async(["ls", "-la", ssh_dir])

        keys = {}
        if result.success:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if "id_" in line and ".pub" in line:
                    parts = line.split()
                    if len(parts) >= 9:
                        filename = parts[-1]
                        keys[filename] = line

        return keys

    async def generate_ssh_key(
        self,
        email: str,
        key_type: str = "ed25519",
        progress_callback: Callable[[str, float], None] | None = None,
    ) -> bool:
        """Generate a new SSH key."""
        try:
            if progress_callback:
                progress_callback("Generating SSH key...", 0.1)

            key_file = f"~/.ssh/id_{key_type}"
            cmd = ["ssh-keygen", "-t", key_type, "-C", email, "-f", key_file, "-N", ""]

            result = await self._executor.run_async(cmd)

            if result.success:
                log.info("Successfully generated SSH key for %s", email)
                if progress_callback:
                    progress_callback("SSH key generated", 1.0)
                return True
            else:
                log.error("Failed to generate SSH key: %s", result.stderr)
                if progress_callback:
                    progress_callback(f"Failed: {result.stderr[:100]}", 0.0)
                return False

        except Exception as e:
            log.exception("Error generating SSH key: %s", e)
            return False
