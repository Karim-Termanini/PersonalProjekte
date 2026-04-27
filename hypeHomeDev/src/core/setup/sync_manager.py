"""HypeDevHome — HypeSync Synchronization Manager.

Implements hierarchical dotfiles synchronization and secret bridging across
host and isolated development environments.
"""

from __future__ import annotations

import abc
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.setup.git_ops import GitOperations
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class SecretConfig:
    """Configuration for secret injection with whitelists."""

    inject_ssh_keys: bool = True
    inject_git_credentials: bool = True
    inject_github_token: bool = False
    ssh_key_whitelist: list[str] = field(default_factory=lambda: ["id_rsa", "id_ed25519"])
    token_whitelist: list[str] = field(default_factory=lambda: ["GITHUB_TOKEN"])


class SyncProvider(abc.ABC):
    """Abstract base for sync providers (GitHub, GitLab, etc.)."""

    @abc.abstractmethod
    async def get_dotfiles_repo(self, username: str) -> str | None:
        """Find the dotfiles repository for a user."""
        pass

    @abc.abstractmethod
    async def get_secrets(self, container_name: str | None = None) -> dict[str, str]:
        """Fetch secrets for the environment."""
        pass


class DotfilesDriver:
    """Handles hierarchical dotfiles detection and application."""

    def __init__(self, executor: HostExecutor, git_ops: GitOperations) -> None:
        self._executor = executor
        self._git_ops = git_ops

    async def apply(self, repo_url: str, target_dir: Path | None = None) -> bool:
        """Apply dotfiles from repo to target_dir (defaults to $HOME)."""
        dotfiles_path = target_dir or (Path.home() / ".dotfiles")
        target_path = target_dir or Path.home()

        # 1. Sync repository
        if not await self._sync_repo(repo_url, dotfiles_path):
            return False

        # 2. Hierarchical Detection & Application
        if await self._apply_chezmoi(dotfiles_path):
            return True
        if await self._apply_stow(dotfiles_path, target_path):
            return True
        if await self._apply_script(dotfiles_path):
            return True

        log.warning("No dotfiles manager or setup script found in %s", dotfiles_path)
        return True

    async def _sync_repo(self, url: str, path: Path) -> bool:
        if path.exists():
            log.info("Updating existing dotfiles at %s", path)
            res = await self._executor.run_async(["git", "-C", str(path), "pull"])
            return res.success

        log.info("Cloning dotfiles from %s", url)
        return await self._git_ops.clone(url, str(path))

    async def _apply_chezmoi(self, path: Path) -> bool:
        """Detect and apply via Chezmoi."""
        has_binary = (await self._executor.run_async(["which", "chezmoi"])).success
        has_marker = (path / ".chezmoiroot").exists() or (path / "chezmoi.yaml").exists()

        if has_binary or has_marker:
            log.info("Chezmoi detected. Applying...")
            res = await self._executor.run_async(["chezmoi", "apply", "--source", str(path)])
            return res.success
        return False

    async def _apply_stow(self, path: Path, target: Path) -> bool:
        """Detect and apply via GNU Stow."""
        if not (await self._executor.run_async(["which", "stow"])).success:
            return False

        log.info("GNU Stow detected. Linking packages...")
        packages = [p.name for p in path.iterdir() if p.is_dir() and not p.name.startswith(".")]
        if not packages:
            return False

        for pkg in packages:
            log.debug("Stowing package: %s", pkg)
            await self._executor.run_async(["stow", "-d", str(path), "-t", str(target), pkg])
        return True

    async def _apply_script(self, path: Path) -> bool:
        """Detect and run custom install script."""
        scripts = ["install.sh", "setup.sh", "bootstrap.sh", "install"]
        for s in scripts:
            script_path = path / s
            if script_path.exists():
                log.info("Running custom setup script: %s", s)
                await self._executor.run_async(["chmod", "+x", str(script_path)])
                res = await self._executor.run_async([str(script_path)], cwd=str(path))
                return res.success
        return False


class SecretsManager:
    """Handles bridging host secrets into isolated environments."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor

    async def bridge_ssh(
        self, container_name: str | None = None, config: SecretConfig | None = None
    ) -> bool:
        """Bridge host SSH agent and/or keys into container."""
        if config and not config.inject_ssh_keys:
            log.info("SSH key bridging disabled by config")
            return True

        if not container_name:
            return True

        log.info("Bridging SSH to %s", container_name)

        # 1. Bridge SSH agent socket (Distrobox shares this automatically)
        cmd = "grep -q 'SSH_AUTH_SOCK' ~/.bashrc || echo 'export SSH_AUTH_SOCK=$SSH_AUTH_SOCK' >> ~/.bashrc"
        res = await self._executor.run_async(
            ["distrobox", "enter", container_name, "--", "bash", "-c", cmd]
        )
        if not res.success:
            log.warning("Failed to bridge SSH_AUTH_SOCK: %s", res.stderr)
            return False

        # 2. Bridge specific SSH keys if whitelisted
        if config and config.ssh_key_whitelist:
            for key_name in config.ssh_key_whitelist:
                key_path = Path.home() / ".ssh" / key_name
                pub_key_path = Path.home() / ".ssh" / f"{key_name}.pub"

                if key_path.exists():
                    log.info("Bridging SSH key: %s", key_name)
                    # Copy private key
                    await self._executor.run_async(
                        [
                            "distrobox",
                            "enter",
                            container_name,
                            "--",
                            "cp",
                            str(key_path),
                            f"~/.ssh/{key_name}",
                        ]
                    )
                    # Copy public key if exists
                    if pub_key_path.exists():
                        await self._executor.run_async(
                            [
                                "distrobox",
                                "enter",
                                container_name,
                                "--",
                                "cp",
                                str(pub_key_path),
                                f"~/.ssh/{key_name}.pub",
                            ]
                        )

        return True

    async def bridge_git_config(
        self, container_name: str | None = None, config: SecretConfig | None = None
    ) -> bool:
        """Copy host global git config to container."""
        if config and not config.inject_git_credentials:
            log.info("Git config bridging disabled by config")
            return True

        if not container_name:
            return True

        log.info("Bridging Git identity to %s", container_name)
        name = (
            await self._executor.run_async(["git", "config", "--global", "user.name"])
        ).stdout.strip()
        email = (
            await self._executor.run_async(["git", "config", "--global", "user.email"])
        ).stdout.strip()

        if name:
            await self._executor.run_async(
                [
                    "distrobox",
                    "enter",
                    container_name,
                    "--",
                    "git",
                    "config",
                    "--global",
                    "user.name",
                    name,
                ]
            )
        if email:
            await self._executor.run_async(
                [
                    "distrobox",
                    "enter",
                    container_name,
                    "--",
                    "git",
                    "config",
                    "--global",
                    "user.email",
                    email,
                ]
            )

        return True

    async def bridge_tokens(
        self, container_name: str | None = None, config: SecretConfig | None = None
    ) -> bool:
        """Bridge API tokens into container."""
        if config and not config.inject_github_token:
            log.info("Token bridging disabled by config")
            return True

        if not container_name:
            return True

        log.info("Bridging API tokens to %s", container_name)

        # Bridge whitelisted tokens
        if config and config.token_whitelist:
            for token_name in config.token_whitelist:
                log.info("Bridging token: %s", token_name)
                # In production, fetch from secure storage
                # For now, export placeholder
                cmd = f"grep -q '{token_name}' ~/.bashrc || echo 'export {token_name}=${token_name}' >> ~/.bashrc"
                await self._executor.run_async(
                    ["distrobox", "enter", container_name, "--", "bash", "-c", cmd]
                )

        return True


class SyncManager:
    """Central hub for HypeSync operations."""

    def __init__(self, executor: HostExecutor, git_ops: GitOperations) -> None:
        self._executor = executor
        self._dotfiles = DotfilesDriver(executor, git_ops)
        self._secrets = SecretsManager(executor)

    async def sync_dotfiles(self, repo_url: str) -> bool:
        """Apply dotfiles to the host."""
        return await self._dotfiles.apply(repo_url)

    async def inject_secrets(
        self, container_name: str | None = None, config: SecretConfig | None = None
    ) -> bool:
        """Bridge identity and secrets to container."""
        ident = await self._secrets.bridge_git_config(container_name, config)
        ssh = await self._secrets.bridge_ssh(container_name, config)
        tokens = await self._secrets.bridge_tokens(container_name, config)
        return ident and ssh and tokens
