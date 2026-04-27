"""HypeDevHome — Stack Manager.

Manages development environment stacks for Distrobox and Toolbx.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.setup.environments import EnvironmentManager
    from core.setup.host_executor import HostExecutor

log = logging.getLogger(__name__)


@dataclass
class StackTemplate:
    """Template for a development stack."""

    id: str
    name: str
    description: str
    icon: str
    image: str
    packages: list[str] = field(default_factory=list)
    init_commands: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    env_vars: dict[str, str] = field(default_factory=dict)
    volumes: list[str] = field(default_factory=list)
    init_script: str | None = None


class StackManager:
    """Handles loading and instantiating development stacks."""

    def __init__(self, executor: HostExecutor, env_manager: EnvironmentManager) -> None:
        self._executor = executor
        self._env_manager = env_manager
        self._stacks: dict[str, StackTemplate] = {}
        self._load_catalog()

        # Container naming constraints
        self._container_name_regex = re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")
        self._max_container_name_length = 64

    def _load_catalog(self) -> None:
        """Load stack templates from JSON catalog."""
        catalog_path = Path(__file__).parent / "stack_catalog_data.json"
        if not catalog_path.exists():
            log.error("Stack catalog not found at: %s", catalog_path)
            return

        try:
            with open(catalog_path) as f:
                data = json.load(f)
                for item in data.get("stacks", []):
                    template = StackTemplate(**item)
                    self._stacks[template.id] = template
            log.info("Loaded %d stack templates", len(self._stacks))
        except Exception as e:
            log.error("Failed to load stack catalog: %s", e)

    def get_available_stacks(self) -> list[StackTemplate]:
        """Get all available stack templates."""
        return list(self._stacks.values())

    def get_stack(self, stack_id: str) -> StackTemplate | None:
        """Get a specific stack template by ID."""
        return self._stacks.get(stack_id)

    def validate_container_name(self, name: str) -> tuple[bool, str]:
        """Validate a container name against Distrobox/Toolbx constraints.

        Args:
            name: Container name to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if not name:
            return False, "Container name cannot be empty"

        if len(name) > self._max_container_name_length:
            return (
                False,
                f"Container name too long (max {self._max_container_name_length} characters)",
            )

        if not self._container_name_regex.match(name):
            return False, (
                "Container name must contain only lowercase letters, numbers, hyphens, and underscores. "
                "Must start and end with alphanumeric character."
            )

        # Check for reserved names
        reserved_names = {"distrobox", "toolbox", "docker", "podman", "root"}
        if name.lower() in reserved_names:
            return False, f"Container name '{name}' is reserved"

        return True, ""

    async def estimate_stack_resources(self, stack_id: str) -> dict:
        """Estimate resource requirements for a stack.

        Args:
            stack_id: ID of the stack to estimate.

        Returns:
            Dictionary with estimated disk space, memory, and time.
        """
        template = self.get_stack(stack_id)
        if not template:
            return {"error": "Stack not found"}

        # Basic estimation based on packages and image
        base_image_size = 500  # MB for base image
        package_size = len(template.packages) * 50  # ~50MB per package
        estimated_disk_mb = base_image_size + package_size

        return {
            "stack_id": stack_id,
            "stack_name": template.name,
            "estimated_disk_mb": estimated_disk_mb,
            "estimated_disk_gb": round(estimated_disk_mb / 1024, 1),
            "estimated_memory_mb": 512,  # Default memory
            "estimated_time_seconds": 120
            + (len(template.packages) * 5),  # Base + package install time
            "package_count": len(template.packages),
            "init_command_count": len(template.init_commands),
            "exports_count": len(template.exports),
        }

    async def instantiate_stack(
        self,
        stack_id: str,
        container_name: str | None = None,
        use_distrobox: bool = True,
        custom_volumes: list[str] | None = None,
        custom_env_vars: dict[str, str] | None = None,
        enable_rollback: bool = True,
    ) -> bool:
        """Create a container from a stack template with potential rollback.

        Args:
            stack_id: ID of the stack to instantiate.
            container_name: Custom name (defaults to stack ID).
            use_distrobox: Whether to use Distrobox (recommended) or Toolbx.
            custom_volumes: Additional volume mounts.
            custom_env_vars: Additional environment variables.
            enable_rollback: Whether to automatically clean up on failure.

        Returns:
            True if creation succeeded.
        """
        template = self.get_stack(stack_id)
        if not template:
            log.error("Stack template not found: %s", stack_id)
            return False

        name = container_name or template.id
        log.info("Instantiating stack '%s' as container '%s'", template.name, name)

        # Track steps for rollback
        completed_steps = []

        try:
            # 1. Create container
            if use_distrobox:
                success = await self._env_manager.create_distrobox(
                    name,
                    image=template.image,
                    volumes=template.volumes + (custom_volumes or []),
                    env_vars={**template.env_vars, **(custom_env_vars or {})},
                )
            else:
                success = await self._env_manager.create_toolbox(name)

            if not success:
                log.error("Failed to create container for stack %s", template.name)
                return False
            completed_steps.append("container_created")

            # 2. Install packages
            if template.packages:
                log.info("Installing packages in stack %s: %s", name, template.packages)
                success = await self._install_packages_in_container(name, template)
                if not success:
                    log.warning("Package installation had issues, continuing anyway...")

            # 3. Run init script or commands
            if template.init_script:
                log.info("Running init script for stack %s", name)
                success = await self._run_init_script(name, template.init_script)
                if not success:
                    raise RuntimeError(f"Init script failed for {name}")
                completed_steps.append("init_script_executed")
            elif template.init_commands:
                for cmd in template.init_commands:
                    success = await self._run_command_in_container(name, cmd)
                    if not success:
                        log.warning("Init command failed: %s", cmd)

            # 4. Export tools (Distrobox only)
            if use_distrobox and template.exports:
                await self._export_tools_from_container(name, template.exports)

            # 5. Set up environment variables
            if template.env_vars or custom_env_vars:
                await self._setup_env_vars_in_container(
                    name, {**template.env_vars, **(custom_env_vars or {})}
                )

            log.info("Stack '%s' instantiated successfully", template.name)
            return True

        except Exception as e:
            log.error("Failed to instantiate stack %s: %s", template.name, e)
            if enable_rollback:
                await self._rollback_stack(name, use_distrobox)
            return False

    async def _rollback_stack(self, container_name: str, use_distrobox: bool) -> None:
        """Phase 5.5: Rollback failed stack instantiation.

        Args:
            container_name: Name of the container to rollback.
            use_distrobox: Whether it's a Distrobox or Toolbx container.
        """
        log.info("Rolling back partial stack %s", container_name)

        try:
            success = False
            if use_distrobox:
                await self._executor.run_async(["distrobox", "stop", container_name, "-Y"])
                await asyncio.sleep(1)
                res = await self._executor.run_async(["distrobox", "rm", "-f", container_name])
                success = res.success
            else:
                res = await self._executor.run_async(["toolbox", "rm", "-f", container_name])
                success = res.success

            if success:
                log.info("Successfully rolled back container %s", container_name)
            else:
                log.warning("Container removal may have failed for %s", container_name)

        except Exception as e:
            log.error("Error during rollback of %s: %s", container_name, e)

    async def check_prerequisites(self) -> dict:
        """Check system prerequisites for stack instantiation.

        Returns:
            Dictionary with check results and recommendations.
        """
        checks = {
            "container_engine": {"status": "pending", "message": "", "required": True},
            "disk_space": {"status": "pending", "message": "", "required": True},
            "network": {"status": "pending", "message": "", "required": True},
            "permissions": {"status": "pending", "message": "", "required": True},
        }

        # Check container engine
        await self._env_manager.initialize()
        if self._env_manager.has_podman or self._env_manager.has_docker:
            checks["container_engine"]["status"] = "ok"
            checks["container_engine"]["message"] = "Container engine available"
        else:
            checks["container_engine"]["status"] = "warning"
            checks["container_engine"]["message"] = (
                "No container engine found. Will attempt installation."
            )

        # Check disk space (simplified)
        try:
            import shutil

            _total, _used, free = shutil.disk_usage("/")
            free_gb = free / (1024**3)
            if free_gb > 10:  # 10GB minimum
                checks["disk_space"]["status"] = "ok"
                checks["disk_space"]["message"] = f"Disk space OK ({free_gb:.1f}GB free)"
            else:
                checks["disk_space"]["status"] = "warning"
                checks["disk_space"]["message"] = f"Low disk space ({free_gb:.1f}GB free)"
        except Exception:
            checks["disk_space"]["status"] = "unknown"
            checks["disk_space"]["message"] = "Could not check disk space"

        # Check network (simplified)
        try:
            import socket

            socket.create_connection(("8.8.8.8", 53), timeout=3)
            checks["network"]["status"] = "ok"
            checks["network"]["message"] = "Network connectivity OK"
        except Exception:
            checks["network"]["status"] = "warning"
            checks["network"]["message"] = "Network may be unavailable"

        # Check permissions
        try:
            import os

            if os.geteuid() == 0:
                checks["permissions"]["status"] = "warning"
                checks["permissions"]["message"] = "Running as root - not recommended"
            else:
                checks["permissions"]["status"] = "ok"
                checks["permissions"]["message"] = "Running as regular user"
        except Exception:
            checks["permissions"]["status"] = "unknown"
            checks["permissions"]["message"] = "Could not check permissions"

        return checks

    async def _install_packages_in_container(
        self, container_name: str, template: StackTemplate
    ) -> bool:
        """Install packages inside a container."""
        pkg_cmd = ["distrobox", "enter", container_name, "--"]

        # Detect package manager based on image
        if "fedora" in template.image or "centos" in template.image or "rhel" in template.image:
            pkg_cmd.extend(["sudo", "dnf", "install", "-y", *template.packages])
        elif "ubuntu" in template.image or "debian" in template.image:
            pkg_cmd.extend(
                ["sudo", "apt", "update", "&&", "sudo", "apt", "install", "-y", *template.packages]
            )
        elif "arch" in template.image:
            pkg_cmd.extend(["sudo", "pacman", "-S", "--noconfirm", *template.packages])
        else:
            log.warning("Unknown base image, trying apt as fallback")
            pkg_cmd.extend(
                ["sudo", "apt", "update", "&&", "sudo", "apt", "install", "-y", *template.packages]
            )

        result = await self._executor.run_async(pkg_cmd)
        return result.success

    async def _run_command_in_container(self, container_name: str, command: str) -> bool:
        """Run a command inside a container."""
        enter_cmd = ["distrobox", "enter", container_name, "--", "bash", "-c", command]
        result = await self._executor.run_async(enter_cmd)
        return result.success

    async def _run_init_script(self, container_name: str, script_content: str) -> bool:
        """Run an init script inside a container."""
        # Write script to temp file
        script_path = f"/tmp/init_{container_name}.sh"
        write_cmd = [
            "distrobox",
            "enter",
            container_name,
            "--",
            "bash",
            "-c",
            f"cat > {script_path} << 'EOF'\n{script_content}\nEOF",
        ]

        result = await self._executor.run_async(write_cmd)
        if not result.success:
            return False

        # Make executable and run
        chmod_cmd = ["distrobox", "enter", container_name, "--", "chmod", "+x", script_path]
        run_cmd = ["distrobox", "enter", container_name, "--", "bash", script_path]

        await self._executor.run_async(chmod_cmd)
        result = await self._executor.run_async(run_cmd)
        return result.success

    async def _export_tools_from_container(self, container_name: str, tools: list[str]) -> None:
        """Export tools from a Distrobox container to the host."""
        for tool in tools:
            log.info("Exporting tool %s from container %s", tool, container_name)
            export_cmd = [
                "distrobox",
                "enter",
                container_name,
                "--",
                "distrobox-export",
                "--bin",
                f"/usr/bin/{tool}",
            ]
            await self._executor.run_async(export_cmd)

    async def _setup_env_vars_in_container(
        self, container_name: str, env_vars: dict[str, str]
    ) -> None:
        """Set up environment variables in a container."""
        for key, value in env_vars.items():
            # Add to .bashrc
            cmd = f"echo 'export {key}={shlex.quote(value)}' >> ~/.bashrc"
            await self._run_command_in_container(container_name, cmd)

            # Also set for current session
            set_cmd = f"export {key}={shlex.quote(value)}"
            await self._run_command_in_container(container_name, set_cmd)

    async def list_running_stacks(self) -> list[dict]:
        """Get information about currently running stacks."""
        envs = await self._env_manager.list_environments()
        stacks = []

        for env_name in envs:
            # Try to match with our known stacks
            template = None
            for stack in self._stacks.values():
                if stack.id in env_name or stack.name.lower().replace(" ", "_") in env_name:
                    template = stack
                    break

            stacks.append(
                {
                    "name": env_name,
                    "template": template.name if template else "Unknown",
                    "status": "running",
                }
            )

        return stacks

    async def stop_stack(self, container_name: str) -> bool:
        """Stop a running stack container."""
        log.info("Stopping stack container: %s", container_name)
        result = await self._executor.run_async(["distrobox", "stop", container_name, "-Y"])
        return result.success

    async def remove_stack(self, container_name: str) -> bool:
        """Remove a stack container."""
        log.info("Removing stack container: %s", container_name)
        result = await self._executor.run_async(["distrobox", "rm", container_name, "-f"])
        return result.success

    async def get_stack_status(self, container_name: str) -> dict:
        """Get detailed status of a stack container."""
        # Check if container exists
        check_cmd = ["distrobox", "list", "--no-header"]
        result = await self._executor.run_async(check_cmd)

        status = {"name": container_name, "exists": False, "running": False, "template": None}

        if result.success:
            for line in result.stdout.splitlines():
                if container_name in line:
                    status["exists"] = True
                    status["running"] = "Up" in line or "running" in line
                    break

        return status
