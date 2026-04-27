"""HypeDevHome — Environments Manager.

Handles Distrobox, Toolbx, Dev Containers, and cloud environment detection
and management.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class DevContainerConfig:
    """Configuration for a development container."""

    name: str
    image: str
    workspace_folder: str = "/workspace"
    extensions: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    customizations: dict = field(default_factory=dict)


@dataclass
class CloudEnvironment:
    """Cloud development environment placeholder."""

    name: str
    description: str
    url_template: str
    available: bool = False
    coming_soon: bool = True


class EnvironmentManager:
    """Manages containerized and cloud development environments on the host."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor
        self.has_distrobox = False
        self.has_toolbx = False
        self.has_podman = False
        self.has_docker = False
        self.has_devcontainer_cli = False

    async def initialize(self) -> None:
        """Detect available environment tools on the host."""
        self.has_distrobox = (await self._executor.run_async(["which", "distrobox"])).success
        self.has_toolbx = (await self._executor.run_async(["which", "toolbox"])).success
        self.has_podman = (await self._executor.run_async(["which", "podman"])).success
        self.has_docker = (await self._executor.run_async(["which", "docker"])).success
        self.has_devcontainer_cli = (
            await self._executor.run_async(["which", "devcontainer"])
        ).success

        log.info(
            "Environments detected: Distrobox=%s, Toolbx=%s, Podman=%s, Docker=%s, DevContainer CLI=%s",
            self.has_distrobox,
            self.has_toolbx,
            self.has_podman,
            self.has_docker,
            self.has_devcontainer_cli,
        )

    async def create_distrobox(
        self,
        name: str,
        image: str = "fedora:latest",
        volumes: list[str] | None = None,
        env_vars: dict[str, str] | None = None,
        init_hooks: list[str] | None = None,
        home_mount: str | None = None,
        additional_flags: list[str] | None = None,
    ) -> bool:
        """Create a new Distrobox container with advanced options.

        Args:
            name: Container name.
            image: Container image (e.g., "fedora:latest", "ubuntu:22.04").
            volumes: Additional volume mounts (e.g., ["/host/path:/container/path"]).
            env_vars: Environment variables to set in container.
            init_hooks: Commands to run after container creation.
            home_mount: Custom home directory mount (defaults to sharing host home).
            additional_flags: Additional distrobox create flags.

        Returns:
            True if creation succeeded.
        """
        if not self.has_distrobox:
            log.error("Distrobox not found on host.")
            # Try to install automatically
            if not await self.install_distrobox():
                return False

        # Build command
        cmd = ["distrobox", "create", "-n", name, "-i", image, "-Y"]

        # Add volumes
        if volumes:
            for volume in volumes:
                cmd.extend(["-v", volume])

        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                cmd.extend(["--env", f"{key}={value}"])

        # Custom home mount
        if home_mount:
            cmd.extend(["--home", home_mount])

        # Additional flags
        if additional_flags:
            cmd.extend(additional_flags)

        log.info("Creating Distrobox: %s (image: %s)", name, image)
        result = await self._executor.run_async(cmd)

        if not result.success:
            log.error("Failed to create Distrobox container: %s", result.stderr)
            return False

        # Run init hooks if provided
        if init_hooks and result.success:
            for hook in init_hooks:
                log.info("Running init hook in %s: %s", name, hook)
                hook_cmd = ["distrobox", "enter", name, "--", "bash", "-c", hook]
                await self._executor.run_async(hook_cmd)

        return result.success

    async def list_environments(self) -> list[dict[str, str]]:
        """List existing Distrobox/Toolbx environments with status.

        Returns:
            List of dicts with name, engine, and status.
        """
        envs = []
        if self.has_distrobox:
            result = await self._executor.run_async(["distrobox", "list", "--no-header"])
            if result.success:
                for line in result.stdout.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 4:
                        envs.append(
                            {
                                "name": parts[1].strip(),
                                "status": parts[3].strip(),
                                "image": parts[2].strip(),
                                "engine": "distrobox",
                            }
                        )
        if self.has_toolbx:
            result = await self._executor.run_async(["toolbox", "list", "--containers"])
            if result.success:
                # Toolbox output: ID IMAGE CREATED STATUS NAME
                for line in result.stdout.splitlines():
                    if "IMAGE" in line:
                        continue
                    parts = line.split()
                    if len(parts) >= 5:
                        envs.append(
                            {
                                "name": parts[4].strip(),
                                "status": parts[3].strip(),
                                "engine": "toolbox",
                            }
                        )
        return envs

    async def start_container(self, name: str, engine: str = "distrobox") -> bool:
        """Start an existing container."""
        cmd = (
            ["distrobox", "start", name]
            if engine == "distrobox"
            else ["toolbox", "enter", name, "--", "true"]
        )
        result = await self._executor.run_async(cmd)
        return result.success

    async def stop_container(self, name: str, engine: str = "distrobox") -> bool:
        """Stop a running container."""
        if engine == "distrobox":
            cmd = ["distrobox", "stop", name, "-Y"]
        else:
            # Toolbox doesn't have a direct 'stop', we kill the podman/docker container
            cmd = ["podman", "stop", name] if self.has_podman else ["docker", "stop", name]
        result = await self._executor.run_async(cmd)
        return result.success

    async def remove_container(self, name: str, engine: str = "distrobox") -> bool:
        """Remove a container."""
        if engine == "distrobox":
            cmd = ["distrobox", "rm", "-f", name]
        else:
            cmd = ["toolbox", "rm", "-f", name]
        result = await self._executor.run_async(cmd)
        return result.success

    async def get_container_stats(self, name: str) -> dict[str, float]:
        """Get CPU, Memory, Network, and Disk stats for a container via podman/docker stats."""
        stats = {
            "cpu_percent": 0.0,
            "mem_usage_mb": 0.0,
            "mem_limit_mb": 0.0,
            "net_io_mb": 0.0,
            "block_io_mb": 0.0,
        }

        engine_cmd = "podman" if self.has_podman else "docker" if self.has_docker else None
        if not engine_cmd:
            return stats

        # Stats in JSON format for easier parsing
        cmd = [engine_cmd, "stats", "--no-stream", "--format", "json", name]
        result = await self._executor.run_async(cmd)

        if result.success and result.stdout:
            try:
                data = json.loads(result.stdout)
                # podman stats can return a list or a single object
                if isinstance(data, list):
                    if not data:
                        return stats
                    data = data[0]

                # Parse CPU (usually a string like "1.23%")
                cpu_str = str(data.get("CPUPerc", "0%")).replace("%", "")
                stats["cpu_percent"] = float(cpu_str)

                # Parse Memory (usually a string like "120MB / 2GB")
                mem_str = str(data.get("MemUsage", "0B / 0B"))
                if " / " in mem_str:
                    usage_part, limit_part = mem_str.split(" / ")
                    stats["mem_usage_mb"] = self._parse_size_to_mb(usage_part)
                    stats["mem_limit_mb"] = self._parse_size_to_mb(limit_part)

                # Parse Network I/O (usually "1MB / 2MB")
                net_str = str(data.get("NetIO", "0B / 0B"))
                if " / " in net_str:
                    rx_part, tx_part = net_str.split(" / ")
                    # We store total I/O (RX + TX) for the default sparkline
                    stats["net_io_mb"] = self._parse_size_to_mb(rx_part) + self._parse_size_to_mb(
                        tx_part
                    )

                # Parse Block I/O (usually "0B / 0B")
                block_str = str(data.get("BlockIO", "0B / 0B"))
                if " / " in block_str:
                    read_part, write_part = block_str.split(" / ")
                    stats["block_io_mb"] = self._parse_size_to_mb(
                        read_part
                    ) + self._parse_size_to_mb(write_part)

            except (json.JSONDecodeError, ValueError, IndexError) as e:
                log.warning("Failed to parse container stats for %s: %s", name, e)

        return stats

    def _parse_size_to_mb(self, size_str: str) -> float:
        """Convert container size strings (e.g. 1.5GB, 120MB) to MB float."""
        size_str = size_str.upper().replace("B", "")
        factor = 1.0
        if "G" in size_str:
            factor = 1024.0
            size_str = size_str.replace("G", "")
        elif "M" in size_str:
            factor = 1.0
            size_str = size_str.replace("M", "")
        elif "K" in size_str:
            factor = 1.0 / 1024.0
            size_str = size_str.replace("K", "")

        try:
            return float(size_str.strip()) * factor
        except ValueError:
            return 0.0

    # DevContainer Support

    async def generate_devcontainer_config(
        self,
        workspace_path: str,
        image: str = "mcr.microsoft.com/devcontainers/base:ubuntu",
        extensions: list[str] | None = None,
    ) -> DevContainerConfig:
        """Generate a devcontainer.json configuration file.

        Args:
            workspace_path: Path to the workspace directory.
            image: Docker image to use.
            extensions: VS Code extensions to install.

        Returns:
            DevContainerConfig object.
        """
        if extensions is None:
            extensions = [
                "ms-python.python",
                "ms-vscode.go",
                "dbaeumer.vscode-eslint",
            ]

        config = DevContainerConfig(
            name="HypeDevHome DevContainer",
            image=image,
            workspace_folder="/workspace",
            extensions=extensions,
            features=[
                "ghcr.io/devcontainers/features/git:1",
                "ghcr.io/devcontainers/features/github-cli:1",
            ],
        )

        return config

    async def create_devcontainer(self, workspace_path: str, config: DevContainerConfig) -> bool:
        """Create a devcontainer from configuration.

        Args:
            workspace_path: Path to the workspace.
            config: DevContainerConfig object.

        Returns:
            True if creation succeeded.
        """
        devcontainer_dir = os.path.join(workspace_path, ".devcontainer")
        config_file = os.path.join(devcontainer_dir, "devcontainer.json")

        # Create .devcontainer directory
        mkdir_result = await self._executor.run_async(["mkdir", "-p", devcontainer_dir])
        if not mkdir_result.success:
            log.error("Failed to create .devcontainer directory: %s", mkdir_result.stderr)
            return False

        # Generate devcontainer.json
        devcontainer_json = {
            "name": config.name,
            "image": config.image,
            "workspaceFolder": config.workspace_folder,
            "customizations": {
                "vscode": {
                    "extensions": config.extensions,
                }
            },
        }

        if config.features:
            devcontainer_json["features"] = {f: {} for f in config.features}

        # Write config file
        json_str = json.dumps(devcontainer_json, indent=2)
        write_result = await self._executor.run_async(
            ["bash", "-c", f"echo '{json_str}' > '{config_file}'"]
        )
        if not write_result.success:
            log.error("Failed to write devcontainer.json: %s", write_result.stderr)
            return False

        log.info("Created devcontainer.json at: %s", config_file)

        # Use devcontainer CLI to open if available
        if self.has_devcontainer_cli:
            log.info("Opening devcontainer with CLI...")
            result = await self._executor.run_async(["devcontainer", "open", workspace_path])
            return result.success

        log.info("devcontainer CLI not available. Config created but container not started.")
        return True

    async def detect_devcontainer(self, workspace_path: str) -> bool:
        """Check if a workspace already has a devcontainer configuration.

        Args:
            workspace_path: Path to the workspace.

        Returns:
            True if devcontainer.json exists.
        """
        config_file = os.path.join(workspace_path, ".devcontainer", "devcontainer.json")
        check_result = await self._executor.run_async(["test", "-f", config_file])
        return check_result.success

    # Cloud Environment Placeholders

    def get_cloud_environments(self) -> list[CloudEnvironment]:
        """Get list of cloud development environments (placeholders).

        Returns:
            List of CloudEnvironment objects.
        """
        return [
            CloudEnvironment(
                name="GitHub Codespaces",
                description="Cloud-hosted development environment with VS Code",
                url_template="https://github.com/codespaces/new?repo={repo}",
                available=False,
                coming_soon=True,
            ),
            CloudEnvironment(
                name="Gitpod",
                description="Automated cloud development environments",
                url_template="https://gitpod.io/#{repo}",
                available=False,
                coming_soon=True,
            ),
            CloudEnvironment(
                name="AWS Cloud9",
                description="Cloud-based IDE with terminal and debugger",
                url_template="https://console.aws.amazon.com/cloud9/",
                available=False,
                coming_soon=True,
            ),
        ]

    def get_container_tools(self) -> dict[str, bool]:
        """Get availability of container-related tools.

        Returns:
            Dict mapping tool names to their availability.
        """
        return {
            "distrobox": self.has_distrobox,
            "toolbox": self.has_toolbx,
            "podman": self.has_podman,
            "docker": self.has_docker,
            "devcontainer-cli": self.has_devcontainer_cli,
        }

    async def install_distrobox(self) -> bool:
        """Install Distrobox on the host system.

        Returns:
            True if installation succeeded.
        """
        log.info("Installing Distrobox...")

        # Check for package manager
        if self.has_distrobox:
            log.info("Distrobox is already installed")
            return True

        # Try different package managers
        install_commands = [
            (["apt", "install", "-y", "distrobox"], "apt"),
            (["dnf", "install", "-y", "distrobox"], "dnf"),
            (["pacman", "-S", "--noconfirm", "distrobox"], "pacman"),
        ]

        for cmd, pkg_manager in install_commands:
            result = await self._executor.run_async(cmd, root=True)
            if result.success:
                log.info("Distrobox installed via %s", pkg_manager)
                self.has_distrobox = True
                return True

        # Fallback: curl install script
        log.info("Package manager installation failed, trying curl installer...")
        install_script = "curl -s https://raw.githubusercontent.com/89luca89/distrobox/main/install | sh -s -- --prefix $HOME/.local"
        result = await self._executor.run_async(["bash", "-c", install_script])
        if result.success:
            self.has_distrobox = True
            return True

        log.error("Failed to install Distrobox")
        return False

    async def create_toolbox(self, name: str = "devbox") -> bool:
        """Create a new Toolbx container.

        Args:
            name: Name for the Toolbx container.

        Returns:
            True if creation succeeded.
        """
        if not self.has_toolbx:
            log.error("Toolbx not found on host.")
            return False

        log.info("Creating Toolbx: %s", name)
        result = await self._executor.run_async(["toolbox", "create", "-y", name])
        return result.success

    async def install_podman(self) -> bool:
        """Install Podman on the host system."""
        log.info("Installing Podman...")
        if self.has_podman:
            return True

        install_commands = [
            (["apt", "install", "-y", "podman"], "apt"),
            (["dnf", "install", "-y", "podman"], "dnf"),
            (["pacman", "-S", "--noconfirm", "podman"], "pacman"),
        ]

        for cmd, pkg_manager in install_commands:
            result = await self._executor.run_async(cmd, root=True)
            if result.success:
                log.info("Podman installed via %s", pkg_manager)
                self.has_podman = True
                return True

        return False

    async def install_docker(self) -> bool:
        """Install Docker on the host system."""
        log.info("Installing Docker...")
        if self.has_docker:
            return True

        # Simplified docker install (engine only)
        install_commands = [
            (["apt", "install", "-y", "docker.io"], "apt"),
            (["dnf", "install", "-y", "docker"], "dnf"),
            (["pacman", "-S", "--noconfirm", "docker"], "pacman"),
        ]

        for cmd, pkg_manager in install_commands:
            result = await self._executor.run_async(cmd, root=True)
            if result.success:
                log.info("Docker installed via %s", pkg_manager)
                self.has_docker = True
                return True

        return False

    # Distrobox-specific advanced features

    async def export_distrobox_app(
        self, container_name: str, app_name: str, desktop_entry: bool = True
    ) -> bool:
        """Export an application from Distrobox container to host.

        Args:
            container_name: Name of the Distrobox container.
            app_name: Name of the application to export.
            desktop_entry: Whether to create a desktop entry.

        Returns:
            True if export succeeded.
        """
        if not self.has_distrobox:
            return False

        cmd = ["distrobox", "enter", container_name, "--", "distrobox-export", "--app", app_name]
        if desktop_entry:
            cmd.append("--desktop")

        result = await self._executor.run_async(cmd)
        return result.success

    async def upgrade_distrobox_container(self, container_name: str) -> bool:
        """Upgrade packages inside a Distrobox container.

        Args:
            container_name: Name of the container to upgrade.

        Returns:
            True if upgrade succeeded.
        """
        if not self.has_distrobox:
            return False

        # First check container image to determine package manager
        list_cmd = ["distrobox", "list", "--no-header"]
        result = await self._executor.run_async(list_cmd)

        if not result.success:
            return False

        # Parse output to find image
        image = "fedora:latest"  # default
        for line in result.stdout.splitlines():
            if container_name in line:
                parts = line.split()
                if len(parts) > 2:
                    image = parts[2]
                break

        # Determine upgrade command based on image
        upgrade_cmd = ["distrobox", "enter", container_name, "--"]
        if "fedora" in image or "centos" in image or "rhel" in image:
            upgrade_cmd.extend(["sudo", "dnf", "upgrade", "-y"])
        elif "ubuntu" in image or "debian" in image:
            upgrade_cmd.extend(["sudo", "apt", "update", "&&", "sudo", "apt", "upgrade", "-y"])
        elif "arch" in image:
            upgrade_cmd.extend(["sudo", "pacman", "-Syu", "--noconfirm"])
        else:
            log.warning("Unknown image type for upgrade: %s", image)
            upgrade_cmd.extend(["sudo", "apt", "update", "&&", "sudo", "apt", "upgrade", "-y"])

        result = await self._executor.run_async(upgrade_cmd)
        return result.success

    async def backup_distrobox_container(
        self, container_name: str, backup_path: str | None = None
    ) -> bool:
        """Backup a Distrobox container to a tar archive.

        Args:
            container_name: Name of the container to backup.
            backup_path: Path to save backup (default: ~/distrobox_backups/{name}.tar)

        Returns:
            True if backup succeeded.
        """
        if not self.has_distrobox:
            return False

        if not backup_path:
            backup_dir = Path.home() / "distrobox_backups"
            backup_dir.mkdir(exist_ok=True)
            backup_path = str(
                backup_dir / f"{container_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tar"
            )

        log.info("Backing up Distrobox container %s to %s", container_name, backup_path)

        # Use distrobox-export to backup
        cmd = ["distrobox", "stop", container_name, "-Y"]
        await self._executor.run_async(cmd)

        # Export container
        export_cmd = ["distrobox", "export", container_name, "--output", backup_path]
        result = await self._executor.run_async(export_cmd)

        # Restart container
        start_cmd = ["distrobox", "start", container_name]
        await self._executor.run_async(start_cmd)

        return result.success

    async def restore_distrobox_container(
        self, backup_path: str, new_name: str | None = None
    ) -> bool:
        """Restore a Distrobox container from a backup.

        Args:
            backup_path: Path to backup tar archive.
            new_name: New name for restored container.

        Returns:
            True if restore succeeded.
        """
        if not self.has_distrobox:
            return False

        if not Path(backup_path).exists():
            log.error("Backup file not found: %s", backup_path)
            return False

        log.info("Restoring Distrobox container from %s", backup_path)

        # Import container
        import_cmd = ["distrobox", "import", backup_path]
        if new_name:
            import_cmd.extend(["--name", new_name])

        result = await self._executor.run_async(import_cmd)
        return result.success

    async def ensure_container_engine(self) -> bool:
        """Ensure a container engine (Podman or Docker) is available.

        Tries Podman first, then Docker as fallback.

        Returns:
            True if a container engine is available.
        """
        if self.has_podman or self.has_docker:
            return True

        log.info("No container engine found, attempting to install Podman...")

        # Try to install Podman first
        if await self.install_podman():
            return True

        log.info("Podman installation failed, trying Docker...")

        # Fallback to Docker
        if await self.install_docker():
            return True

        log.error("Failed to install any container engine")
        return False

    async def get_distrobox_info(self, container_name: str) -> dict:
        """Get detailed information about a Distrobox container.

        Args:
            container_name: Name of the container.

        Returns:
            Dictionary with container information.
        """
        if not self.has_distrobox:
            return {"error": "Distrobox not available"}

        info = {
            "name": container_name,
            "exists": False,
            "running": False,
            "image": None,
            "status": None,
            "created": None,
            "size": None,
        }

        # Get container details
        list_cmd = ["distrobox", "list", "--no-header"]
        result = await self._executor.run_async(list_cmd)

        if result.success:
            for line in result.stdout.splitlines():
                if container_name in line:
                    parts = line.split()
                    info["exists"] = True
                    info["running"] = "Up" in line or "running" in line
                    if len(parts) > 2:
                        info["image"] = parts[2]
                    if len(parts) > 3:
                        info["created"] = parts[3]
                    if len(parts) > 4:
                        info["size"] = parts[4]
                    break

        return info
