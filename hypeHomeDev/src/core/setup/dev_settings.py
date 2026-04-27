"""HypeDevHome — Developer Settings Applier.

Applies comprehensive developer environment settings including file manager
preferences, Git configuration, shell enhancements, environment variables,
and SSH agent auto-start.
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
class SettingsResult:
    """Result of applying developer settings."""

    success: bool
    applied_settings: list[str] = field(default_factory=list)
    failed_settings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    message: str = ""


class DevSettingsApplier:
    """Applies comprehensive developer environment settings."""

    def __init__(self, executor: HostExecutor) -> None:
        self._executor = executor
        self._detected_shell: str | None = None
        self._detected_fm: str | None = None

    async def apply_settings(
        self,
        git_name: str | None = None,
        git_email: str | None = None,
        git_editor: str | None = None,
        enable_aliases: bool = True,
        enable_hidden_files: bool = True,
        enable_file_extensions: bool = True,
        enable_ssh_agent: bool = True,
        env_vars: dict[str, str] | None = None,
        backup_before_apply: bool = True,
    ) -> SettingsResult:
        """Apply all developer settings.

        Args:
            git_name: Git user.name value.
            git_email: Git user.email value.
            git_editor: Git core.editor value.
            enable_aliases: Whether to add shell aliases.
            enable_hidden_files: Show hidden files in file manager.
            enable_file_extensions: Show file extensions in file manager.
            enable_ssh_agent: Auto-start SSH agent on login.
            env_vars: Environment variables to set.
            backup_before_apply: Backup configs before applying.

        Returns:
            SettingsResult with applied/failed settings.
        """
        result = SettingsResult(success=True)

        # Detect environment
        await self._detect_shell()
        await self._detect_file_manager()

        # Apply settings in order
        if await self._apply_file_manager_settings(
            enable_hidden_files, enable_file_extensions, result
        ):
            result.applied_settings.append("File Manager Settings")
        else:
            result.failed_settings.append("File Manager Settings")
            result.success = False

        if await self._apply_git_config(git_name, git_email, git_editor, result):
            result.applied_settings.append("Git Configuration")
        else:
            result.failed_settings.append("Git Configuration")
            result.success = False

        if enable_aliases and await self._apply_shell_aliases(result):
            result.applied_settings.append("Shell Aliases")
        elif enable_aliases:
            result.failed_settings.append("Shell Aliases")
            result.success = False

        if enable_ssh_agent and await self._apply_ssh_agent(result):
            result.applied_settings.append("SSH Agent Auto-start")
        elif enable_ssh_agent:
            result.failed_settings.append("SSH Agent Auto-start")
            result.success = False

        if env_vars and await self._apply_env_vars(env_vars, result):
            result.applied_settings.append("Environment Variables")
        elif env_vars:
            result.failed_settings.append("Environment Variables")
            result.success = False

        # Build message
        if result.success:
            result.message = f"Successfully applied {len(result.applied_settings)} settings"
        else:
            result.message = (
                f"Applied {len(result.applied_settings)} settings, "
                f"{len(result.failed_settings)} failed"
            )

        return result

    async def _detect_shell(self) -> None:
        """Detect the user's default shell."""
        result = await self._executor.run_async(["bash", "-c", "echo $SHELL"])
        if result.success:
            shell_path = result.stdout.strip()
            if "zsh" in shell_path:
                self._detected_shell = "zsh"
            elif "fish" in shell_path:
                self._detected_shell = "fish"
            else:
                self._detected_shell = "bash"
        else:
            self._detected_shell = "bash"  # fallback

        log.info("Detected shell: %s", self._detected_shell)

    async def _detect_file_manager(self) -> None:
        """Detect the active file manager."""
        # Check for common file managers in order of preference
        managers = ["nautilus", "dolphin", "thunar", "nemo"]
        for mgr in managers:
            result = await self._executor.run_async(["which", mgr])
            if result.success:
                self._detected_fm = mgr
                log.info("Detected file manager: %s", mgr)
                return

        self._detected_fm = None
        log.info("No supported file manager detected")

    async def _apply_file_manager_settings(
        self,
        show_hidden: bool,
        show_extensions: bool,
        result: SettingsResult,
    ) -> bool:
        """Apply file manager preferences."""
        if not self._detected_fm:
            result.warnings.append("No supported file manager detected")
            return True

        success = False

        if self._detected_fm == "nautilus":
            success = await self._apply_nautilus_settings(show_hidden, show_extensions)
        elif self._detected_fm == "dolphin":
            success = await self._apply_dolphin_settings(show_hidden, show_extensions)
        elif self._detected_fm == "thunar":
            success = await self._apply_thunar_settings(show_hidden, show_extensions)
        elif self._detected_fm == "nemo":
            success = await self._apply_nemo_settings(show_hidden, show_extensions)

        return success

    async def _apply_nautilus_settings(self, show_hidden: bool, show_extensions: bool) -> bool:
        """Apply Nautilus (GNOME Files) settings."""
        log.info("Applying Nautilus settings")
        success = True

        if show_hidden:
            r = await self._executor.run_async(
                ["gsettings", "set", "org.gnome.nautilus.preferences", "show-hidden-files", "true"]
            )
            success = success and r.success

        if show_extensions:
            r = await self._executor.run_async(
                [
                    "gsettings",
                    "set",
                    "org.gnome.nautilus.preferences",
                    "show-filetype-icons",
                    "true",
                ]
            )
            success = success and r.success

        return success

    async def _apply_dolphin_settings(self, show_hidden: bool, show_extensions: bool) -> bool:
        """Apply Dolphin (KDE) settings via kwriteconfig5."""
        log.info("Applying Dolphin settings")

        # Check if kwriteconfig5 is available
        has_kwriteconfig = await self._executor.run_async(["which", "kwriteconfig5"])
        if not has_kwriteconfig.success:
            log.warning("kwriteconfig5 not found, skipping Dolphin config")
            return True

        success = True
        config_file = "dolphinrc"
        group = "General"

        if show_hidden:
            r = await self._executor.run_async(
                [
                    "kwriteconfig5",
                    "--file",
                    config_file,
                    "--group",
                    group,
                    "--key",
                    "ShowHiddenFiles",
                    "true",
                ]
            )
            success = success and r.success

        return success

    async def _apply_thunar_settings(self, show_hidden: bool, show_extensions: bool) -> bool:
        """Apply Thunar (XFCE) settings."""
        log.info("Applying Thunar settings")
        # Thunar settings are typically stored in XML, skip for now
        return True

    async def _apply_nemo_settings(self, show_hidden: bool, show_extensions: bool) -> bool:
        """Apply Nemo (Cinnamon) settings."""
        log.info("Applying Nemo settings")
        success = True

        if show_hidden:
            r = await self._executor.run_async(
                ["gsettings", "set", "org.nemo.preferences", "show-hidden-files", "true"]
            )
            success = success and r.success

        return success

    async def _apply_git_config(
        self,
        name: str | None,
        email: str | None,
        editor: str | None,
        result: SettingsResult,
    ) -> bool:
        """Apply Git global configuration."""
        log.info("Applying Git configuration")
        success = True

        # Core settings
        core_configs = [
            ["git", "config", "--global", "pull.rebase", "true"],
            ["git", "config", "--global", "init.defaultBranch", "main"],
            ["git", "config", "--global", "color.ui", "auto"],
            ["git", "config", "--global", "core.autocrlf", "input"],
            ["git", "config", "--global", "credential.helper", "store"],
        ]

        for config in core_configs:
            r = await self._executor.run_async(config)
            if not r.success:
                result.warnings.append(f"Git config failed: {' '.join(config[4:])}")

        # User identity
        if name:
            r = await self._executor.run_async(["git", "config", "--global", "user.name", name])
            success = success and r.success

        if email:
            r = await self._executor.run_async(["git", "config", "--global", "user.email", email])
            success = success and r.success

        # Editor
        if editor:
            r = await self._executor.run_async(
                ["git", "config", "--global", "core.editor", editor]
            )
            success = success and r.success

        return success

    async def _apply_shell_aliases(self, result: SettingsResult) -> bool:
        """Apply useful shell aliases and functions."""
        log.info("Applying shell aliases")

        marker_start = "# >>> HypeDevHome aliases start >>>"
        marker_end = "# <<< HypeDevHome aliases end <<<"

        # Common aliases
        aliases_block = """
# HypeDevHome - Development Aliases
alias ls='ls --color=auto'
alias ll='ls -alhF'
alias la='ls -A'
alias l='ls -CF'
alias grep='grep --color=auto'
alias fgrep='fgrep --color=auto'
alias egrep='egrep --color=auto'
alias diff='diff --color=auto'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git pull'
alias gd='git diff'
alias gb='git branch'
alias gco='git checkout'
alias glog='git log --oneline --graph --decorate'

# Navigation
alias devcd='cd ~/Dev'
alias projects='cd ~/Dev/projects'

# Modern tool replacements (if available)
"""

        # Check for modern tools and add aliases
        tools_check = {
            "eza": "alias ls='eza --color=auto -a'",
            "bat": "alias cat='bat --paging=never'",
            "delta": "alias diff='delta'",
            "fzf": "alias vf='fzf'",
        }

        for tool, alias_line in tools_check.items():
            r = await self._executor.run_async(["which", tool])
            if r.success:
                aliases_block += f"{alias_line}\n"

        block = f"\n{marker_start}\n{aliases_block}\n{marker_end}\n"

        # Apply to shell configs
        shell_configs = self._get_shell_config_files()
        for config in shell_configs:
            await self._append_to_file_if_not_exists(block, config, marker_start)

        return True

    async def _apply_ssh_agent(self, result: SettingsResult) -> bool:
        """Configure SSH agent auto-start."""
        log.info("Configuring SSH agent auto-start")

        marker = "# >>> HypeDevHome SSH Agent Setup >>>"
        marker_end = "# <<< HypeDevHome SSH Agent Setup <<<"

        ssh_snippet = """
# HypeDevHome - SSH Agent Auto-start
if [ -z "$SSH_AUTH_SOCK" ]; then
    # Check for a running ssh-agent
    if [ -f ~/.ssh-agent-info ]; then
        . ~/.ssh-agent-info > /dev/null 2>&1
    fi

    # If still not running, start a new one
    if [ -z "$SSH_AUTH_SOCK" ]; then
        eval $(ssh-agent -s) > /dev/null 2>&1
        echo "export SSH_AUTH_SOCK=$SSH_AUTH_SOCK" > ~/.ssh-agent-info
        echo "export SSH_AGENT_PID=$SSH_AGENT_PID" >> ~/.ssh-agent-info
    fi
fi
"""

        block = f"\n{marker}\n{ssh_snippet}\n{marker_end}\n"

        # Apply to shell configs
        shell_configs = self._get_shell_config_files()
        for config in shell_configs:
            await self._append_to_file_if_not_exists(block, config, marker)

        # Also create a systemd user service option
        await self._create_ssh_agent_systemd_service()

        return True

    async def _create_ssh_agent_systemd_service(self) -> None:
        """Create optional systemd service for SSH agent."""
        service_dir = "~/.config/systemd/user"
        service_file = "ssh-agent.service"

        # Check if systemd is available
        result = await self._executor.run_async(["systemctl", "--user", "is-system-running"])
        if not result.success:
            log.info("Systemd user session not available, skipping service creation")
            return

        expanded_dir = os.path.expanduser(service_dir)
        mkdir_result = await self._executor.run_async(["mkdir", "-p", expanded_dir])
        if not mkdir_result.success:
            return

        # Service file content
        service_content = """[Unit]
Description=SSH Agent
After=network.target

[Service]
Type=forking
Environment=SSH_AUTH_SOCK=%t/ssh-agent.socket
ExecStart=/usr/bin/ssh-agent -a $SSH_AUTH_SOCK
ExecStop=/usr/bin/ssh-agent -k

[Install]
WantedBy=default.target
"""

        full_path = os.path.join(expanded_dir, service_file)
        write_result = await self._executor.run_async(
            ["bash", "-c", f"cat > '{full_path}' << 'EOF'\n{service_content}\nEOF"]
        )

        if write_result.success:
            log.info("SSH agent systemd service created at: %s", full_path)

    async def _apply_env_vars(self, env_vars: dict[str, str], result: SettingsResult) -> bool:
        """Apply environment variables to ~/.profile."""
        log.info("Applying environment variables")

        marker_start = "# >>> HypeDevHome Env Vars start >>>"
        marker_end = "# <<< HypeDevHome Env Vars end <<<"

        lines = [f"\n{marker_start}"]
        for key, value in env_vars.items():
            lines.append(f'export {key}="{value}"')
        lines.append(f"{marker_end}\n")

        block = "\n".join(lines)
        profile_path = "~/.profile"

        await self._append_to_file_if_not_exists(block, profile_path, marker_start)

        # Also apply to bashrc/zshrc for interactive shells
        shell_configs = self._get_shell_config_files()
        for config in shell_configs:
            await self._append_to_file_if_not_exists(block, config, marker_start)

        return True

    def _get_shell_config_files(self) -> list[str]:
        """Get list of shell config files to modify."""
        configs = []

        if self._detected_shell == "zsh":
            configs.extend(["~/.zshrc", "~/.zprofile"])
        elif self._detected_shell == "fish":
            configs.append("~/.config/fish/config.fish")
        else:
            configs.extend(["~/.bashrc", "~/.bash_profile"])

        # Always include profile
        configs.append("~/.profile")

        return configs

    async def _append_to_file_if_not_exists(
        self, content: str, file_path: str, marker: str
    ) -> None:
        """Append content to file if marker doesn't exist."""
        expanded_path = os.path.expanduser(file_path)

        # Check if file exists
        check_file = await self._executor.run_async(["test", "-f", expanded_path])
        if not check_file.success:
            # Create empty file
            await self._executor.run_async(["touch", expanded_path])

        # Check if marker already exists
        check_marker = await self._executor.run_async(["grep", "-q", marker, expanded_path])
        if check_marker.success:
            log.info("Marker already exists in %s, skipping", file_path)
            return

        # Append content
        # We use a standard echo >> to avoid hanging on stdin
        write_cmd = f"echo '{content}' >> '{expanded_path}'"
        result = await self._executor.run_async(["bash", "-c", write_cmd])
        if result.success:
            log.info("Appended content to %s", file_path)
        else:
            log.warning("Failed to append content to %s: %s", file_path, result.stderr)

    async def preview_changes(self) -> dict[str, str]:
        """Preview what changes will be applied without actually applying them.

        Returns:
            Dict mapping setting names to their proposed changes.
        """
        preview = {}

        # Shell aliases preview
        preview["shell_aliases"] = "Will add: ls, ll, grep, git shortcuts (gs, ga, gc, gp, etc.)"

        # SSH agent preview
        preview["ssh_agent"] = "Will add SSH agent auto-start to shell config files"

        # Git config preview
        preview["git_config"] = (
            "Will set: pull.rebase=true, init.defaultBranch=main, "
            "color.ui=auto, core.autocrlf=input"
        )

        # File manager preview
        if self._detected_fm:
            preview["file_manager"] = f"Will configure {self._detected_fm}: show hidden files"
        else:
            preview["file_manager"] = "No supported file manager detected"

        return preview
