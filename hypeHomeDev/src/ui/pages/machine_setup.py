"""HypeDevHome — Machine Setup Page.

A wizard-style one-click development environment setup.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from app import HypeDevHomeApp

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from pathlib import Path  # noqa: E402

from gi.repository import Gio, GLib, Gtk  # noqa: E402

from core.setup.config_backup import ConfigBackupManager  # noqa: E402
from core.setup.dev_folder import DevFolderCreator  # noqa: E402
from core.setup.dev_settings import DevSettingsApplier  # noqa: E402
from core.setup.environments import EnvironmentManager  # noqa: E402
from core.setup.git_ops import GitOperations  # noqa: E402
from core.setup.host_executor import HostExecutor  # noqa: E402
from core.setup.models import (  # noqa: E402
    SetupConfig,
    SetupStepType,
)
from core.setup.package_installer import PackageInstaller  # noqa: E402
from core.setup.stack_manager import StackManager  # noqa: E402
from core.setup.sync_manager import SyncManager  # noqa: E402
from ui.pages.base_page import BasePage  # noqa: E402
from ui.pages.setup_views import (  # noqa: E402
    AppSelectionView,
    ConfigurationView,
    EnvironmentSelectionView,
    ExecutionLogView,
    RepoEntryView,
    SyncConfigurationView,
)

log = logging.getLogger(__name__)


class MachineSetupPage(BasePage):
    """Wizard-style development environment setup."""

    page_title = "Machine Setup"
    page_icon = "computer-symbolic"

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._executor = HostExecutor()
        self._installer = PackageInstaller(self._executor)
        self._git_ops = GitOperations(self._executor)
        self._envs = EnvironmentManager(self._executor)

        # Agent C components
        self._dev_folder_creator = DevFolderCreator(self._executor)
        self._dev_settings_applier = DevSettingsApplier(self._executor)
        self._config_backup = ConfigBackupManager(self._executor)

        # Phase 5 managers
        self._stack_manager = StackManager(self._executor, self._envs)
        self._sync_manager = SyncManager(self._executor, self._git_ops)

        self._config = SetupConfig(apps=[])
        self._current_step = SetupStepType.APPS
        self._setup_task: concurrent.futures.Future[Any] | None = None
        self._init_task: concurrent.futures.Future[Any] | None = None
        self._preflight_task: concurrent.futures.Future[Any] | None = None

    def build_content(self) -> None:
        # Main layout
        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        # Step 1: Apps
        self._app_view = AppSelectionView(self._config.apps)
        self._stack.add_titled(self._app_view, "apps", "Applications")

        # Step 2: Repos
        self._repo_view = RepoEntryView(self._config.repos)
        self._stack.add_titled(self._repo_view, "repos", "Repositories")

        # Step 3: Environments (New in Phase 5)
        self._env_view = EnvironmentSelectionView(self._config)
        self._stack.add_titled(self._env_view, "environments", "Environments")

        # Step 4: Sync (New in Phase 5)
        self._sync_view = SyncConfigurationView(self._config)
        self._stack.add_titled(self._sync_view, "sync", "Sync")

        # Step 5: Config
        self._config_view = ConfigurationView(
            self._config,
            backup_manager=self._config_backup,
            settings_applier=self._dev_settings_applier,
        )
        self._stack.add_titled(self._config_view, "config", "Configuration")

        # Step 6: Execution
        self._log_view = ExecutionLogView()
        self._stack.add_titled(self._log_view, "execution", "Installation")

        # Navigation Header
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        nav_box.set_halign(Gtk.Align.END)
        nav_box.set_valign(Gtk.Align.END)
        nav_box.set_margin_bottom(12)
        nav_box.set_margin_end(12)

        self._back_btn = Gtk.Button(label="Back")
        self._back_btn.add_css_class("outlined")
        self._back_btn.set_visible(False)
        self._back_btn.connect("clicked", self._on_back_clicked)
        nav_box.append(self._back_btn)

        self._nav_btn = Gtk.Button(label="Next")
        self._nav_btn.add_css_class("suggested-action")
        self._nav_btn.connect("clicked", self._on_nav_clicked)
        nav_box.append(self._nav_btn)

        overlay = Gtk.Overlay()
        overlay.set_child(self._stack)
        overlay.add_overlay(nav_box)

        page_root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page_root.set_margin_start(12)
        page_root.set_margin_end(12)

        intro_title = Gtk.Label(label="Machine setup wizard")
        intro_title.add_css_class("title-2")
        intro_title.set_halign(Gtk.Align.START)

        intro_body = Gtk.Label(
            label=(
                "Each step below has its own explanation. "
                "Nothing is mandatory — skip with Next. "
                "Git name, email, and dev folder are prefilled on the Configuration step when possible."
            )
        )
        intro_body.set_wrap(True)
        intro_body.set_xalign(0)
        intro_body.add_css_class("dim-label")

        page_root.append(intro_title)
        page_root.append(intro_body)
        page_root.append(overlay)

        self.append(page_root)

        # Initialization
        app = cast("HypeDevHomeApp", Gio.Application.get_default())
        if app:
            self._init_task = app.enqueue_task(self._initialize_setup())

    async def _initialize_setup(self) -> None:
        """Load catalog and check status."""
        await self._prefill_from_host()

        # Only initialize once per session to preserve selections
        if self._config.apps and any(a.description for a in self._config.apps):
            log.info("App catalog already initialized, skipping reload")
            return

        if await self._installer.initialize():
            self._log_view.append_log("📡 Refreshing application catalog...")
            self._config.apps = await self._installer.get_available_packages()
            self._app_view.update_apps(self._config.apps)
            await self._check_installed_apps()

    async def _prefill_from_host(self) -> None:
        """Set git identity + dev folder from this machine when fields still default/empty."""
        c = self._config
        home = Path.home()

        if c.dev_folder in ("~/Dev", "~/dev", ""):
            for candidate in (
                home / "Dev",
                home / "Documents" / "GitHub",
                home / "Documents",
                home / "src",
            ):
                if candidate.is_dir():
                    c.dev_folder = str(candidate)
                    break

        if not c.git_user_name:
            r = await self._executor.run_async(["git", "config", "--global", "user.name"])
            if r.success and r.stdout.strip():
                c.git_user_name = r.stdout.strip()

        if not c.git_user_email:
            r = await self._executor.run_async(["git", "config", "--global", "user.email"])
            if r.success and r.stdout.strip():
                c.git_user_email = r.stdout.strip()

        GLib.idle_add(self._config_view.apply_prefill_to_rows)

    async def _check_installed_apps(self) -> None:
        """Initial check to see what's already on the system."""
        for app in self._config.apps:
            if await self._installer.is_installed(app):
                # We could mark as selected = False or show a badge
                pass

    async def _run_preflight_checks(self) -> None:
        """Phase 5.5: Verification checks before final summary."""
        summary = "<b>Ready to Setup:</b>\n"
        summary += f"• Apps: {len([a for a in self._config.apps if a.selected])} selected\n"
        summary += f"• Repos: {len(self._config.repos)} added\n"
        summary += f"• Stacks: {len(self._config.selected_stacks)} isolated environments\n\n"

        summary += "<b>Pre-flight Verification:</b>\n"

        # 1. Check Git
        res = await self._executor.run_async(["which", "git"])
        summary += f"{'✅' if res.success else '❌'} Git installed\n"

        # 2. Check Container Engine
        await self._envs.initialize()
        has_engine = self._envs.has_distrobox or self._envs.has_toolbx
        summary += f"{'✅' if has_engine else '⚠️'} Container engine found\n"

        # 3. Check SSH Key
        ssh_dir = Path.home() / ".ssh"
        has_keys = any(ssh_dir.iterdir()) if ssh_dir.exists() else False
        summary += f"{'✅' if has_keys else '⚠️'} Host SSH identity found\n"

        # 4. Check Dotfiles repo (if applicable)
        if self._config.sync_dotfiles and self._config.dotfiles_url:
            summary += f"🔗 HypeSync: {self._config.dotfiles_url[:25]}...\n"

        self._config_view.update_summary(summary)

    def _on_back_clicked(self, _btn: Gtk.Button) -> None:
        """Navigate backward in the setup wizard."""
        if self._current_step == SetupStepType.REPOS:
            self._current_step = SetupStepType.APPS
            self._stack.set_visible_child_name("apps")
            self._back_btn.set_visible(False)
        elif self._current_step == SetupStepType.ENVIRONMENTS:
            self._current_step = SetupStepType.REPOS
            self._stack.set_visible_child_name("repos")
        elif self._current_step == SetupStepType.SYNC:
            self._current_step = SetupStepType.ENVIRONMENTS
            self._stack.set_visible_child_name("environments")
        elif self._current_step == SetupStepType.CONFIG:
            self._current_step = SetupStepType.SYNC
            self._stack.set_visible_child_name("sync")
            self._nav_btn.set_label("Next")
        elif self._current_step == SetupStepType.EXECUTION:
            # Cannot go back from execution easily,
            # but if it finished we reset to start
            if not self._setup_task or self._setup_task.done():
                self._current_step = SetupStepType.APPS
                self._stack.set_visible_child_name("apps")
                self._back_btn.set_visible(False)
                self._nav_btn.set_label("Next")
                self._nav_btn.add_css_class("suggested-action")
                self._nav_btn.remove_css_class("destructive-action")

    def _on_nav_clicked(self, _btn: Gtk.Button) -> None:
        if self._current_step == SetupStepType.APPS:
            self._current_step = SetupStepType.REPOS
            self._stack.set_visible_child_name("repos")
            self._back_btn.set_visible(True)
        elif self._current_step == SetupStepType.REPOS:
            self._current_step = SetupStepType.ENVIRONMENTS
            self._stack.set_visible_child_name("environments")
        elif self._current_step == SetupStepType.ENVIRONMENTS:
            self._current_step = SetupStepType.SYNC
            self._stack.set_visible_child_name("sync")
        elif self._current_step == SetupStepType.SYNC:
            self._sync_view.sync_config()
            self._current_step = SetupStepType.CONFIG
            self._stack.set_visible_child_name("config")

            # Phase 5.5: Pre-flight Verification
            app = cast("HypeDevHomeApp", Gio.Application.get_default())
            if app:
                self._preflight_task = app.enqueue_task(self._run_preflight_checks())

            self._nav_btn.set_label("Start Setup")
        elif self._current_step == SetupStepType.CONFIG:
            self._config_view.sync_config()
            self._current_step = SetupStepType.EXECUTION
            self._stack.set_visible_child_name("execution")
            self._nav_btn.set_label("Cancel")
            self._nav_btn.remove_css_class("suggested-action")
            self._nav_btn.add_css_class("destructive-action")
            app = cast("HypeDevHomeApp", Gio.Application.get_default())
            if app:
                self._setup_task = app.enqueue_task(self._run_setup())
        elif self._current_step == SetupStepType.EXECUTION:
            # Cancellation logic
            if self._setup_task and not self._setup_task.done():
                self._setup_task.cancel()
                self._log_view.append_log("\n[CANCELLED] Setup task aborted by user.")
                self._nav_btn.set_label("Back to Apps")
                self._nav_btn.remove_css_class("destructive-action")
                self._nav_btn.add_css_class("suggested-action")
                self._current_step = SetupStepType.APPS  # Simplification
            else:
                # Finished, return to Welcome (wizards + overview)
                from ui.window import HypeDevHomeWindow

                root = self.get_root()
                if isinstance(root, HypeDevHomeWindow):
                    root.navigate_to("dashboard")
                else:
                    # Fallback if window not found yet
                    self._stack.set_visible_child_name("apps")
                    self._current_step = SetupStepType.APPS
                    self._nav_btn.set_label("Next")

    def _on_open_folder_clicked(self, _btn: Gtk.Button) -> None:
        """Open the dev folder in the default file manager."""
        folder_path = self._config.dev_folder.replace("~", str(Path.home()))
        Gio.AppInfo.launch_default_for_uri(f"file://{folder_path}", None)

    def _on_open_terminal_clicked(self, _btn: Gtk.Button) -> None:
        """Open a terminal in the dev folder."""
        folder_path = self._config.dev_folder.replace("~", str(Path.home()))
        # Try common terminals
        app = cast("HypeDevHomeApp", Gio.Application.get_default())
        if app:
            app.enqueue_task(
                self._executor.run_async(["gnome-terminal", "--working-directory", folder_path])
            )

    async def _run_setup(self) -> None:
        """Main execution sequence with Agent C components."""
        try:
            self._log_view.set_progress(0.05, "Initializing setup...")
            self._log_view.append_log("🚀 Starting HypeDevHome Machine Setup...")
            self._log_view.append_log("-" * 40)

            if not await self._installer.initialize():
                self._log_view.append_log(
                    "Warning: No system package manager detected. Only Flatpaks will be installed."
                )

            # 0. Detect Environments (Distrobox etc)
            self._log_view.set_progress(0.1, "Detecting container engines...")
            await self._envs.initialize()
            if self._envs.has_distrobox or self._envs.has_toolbx:
                env_status = []
                if self._envs.has_distrobox:
                    env_status.append("Distrobox")
                if self._envs.has_toolbx:
                    env_status.append("Toolbx")
                self._log_view.append_log(f"🐳 Container tools detected: {', '.join(env_status)}")

            # 1. Install Apps (Optimized Batch)
            self._log_view.set_progress(0.15, "Installing applications...")
            selected_apps = [app for app in self._config.apps if app.selected]
            if selected_apps:
                self._log_view.append_log(f"📦 Installing {len(selected_apps)} applications...")
                success = await self._installer.install_apps(selected_apps)
                for app in selected_apps:
                    app_status = "DONE" if app.status.name == "COMPLETED" else "FAILED"
                    self._log_view.append_log(f"  [{app_status}] {app.name}")
            else:
                self._log_view.append_log("(i) No applications selected for installation.")

            # 2. Create Dev Folder with Agent C enhanced creator
            self._log_view.set_progress(0.3, "Creating development directory...")
            self._log_view.append_log("📁 Creating development directory...")
            dev_folder_result = await self._dev_folder_creator.create_dev_folder(
                self._config.dev_folder,
                use_btrfs=self._config.btrfs_subvolume,
            )
            if dev_folder_result.success:
                self._log_view.append_log(f"  [DONE] {dev_folder_result.message}")
                if dev_folder_result.btrfs_optimized:
                    self._log_view.append_log("  [BTRFS] Subvolume optimization applied")
                if dev_folder_result.suggestions:
                    for suggestion in dev_folder_result.suggestions:
                        self._log_view.append_log(f"  [TIP] {suggestion}")
            else:
                self._log_view.append_log(
                    f"  [ERROR] Failed to create dev folder: {dev_folder_result.message}"
                )

            # 3. Backup existing configs before applying settings
            self._log_view.set_progress(0.4, "Backing up configurations...")
            self._log_view.append_log("💾 Backing up existing configurations...")
            backup_result = await self._config_backup.create_backup(
                description="Pre-HypeDevHome setup backup"
            )
            if backup_result.success:
                self._log_view.append_log(f"  [DONE] Backup created: {backup_result.message}")
            else:
                self._log_view.append_log(f"  [WARNING] Backup failed: {backup_result.message}")

            # 4. Apply Developer Settings with Agent C comprehensive applier
            self._log_view.set_progress(0.5, "Applying developer settings...")
            self._log_view.append_log("⚙️ Applying developer settings...")
            settings_config = self._config_view.get_settings_config()
            settings_result = await self._dev_settings_applier.apply_settings(
                git_name=settings_config.get("git_name") or self._config.git_user_name,
                git_email=settings_config.get("git_email") or self._config.git_user_email,
                git_editor=settings_config.get("git_editor"),
                enable_aliases=settings_config.get("enable_aliases", True),
                enable_hidden_files=settings_config.get("enable_hidden_files", True),
                enable_file_extensions=settings_config.get("enable_file_extensions", True),
                enable_ssh_agent=settings_config.get(
                    "enable_ssh_agent", self._config.setup_ssh_agent
                ),
                env_vars=self._config.env_vars,
            )

            if settings_result.success:
                self._log_view.append_log(f"  [DONE] {settings_result.message}")
                for setting in settings_result.applied_settings:
                    self._log_view.append_log(f"    ✓ {setting}")
            else:
                self._log_view.append_log(f"  [PARTIAL] {settings_result.message}")
                for setting in settings_result.failed_settings:
                    self._log_view.append_log(f"    ✗ {setting}")
                for warning in settings_result.warnings:
                    self._log_view.append_log(f"    ⚠ {warning}")

            # 5. Clone or update repos (pull when same remote already exists)
            if self._config.repos:
                self._log_view.set_progress(
                    0.65, f"Cloning {len(self._config.repos)} repositories..."
                )
                self._log_view.append_log(f"🔧 Cloning {len(self._config.repos)} repositories...")
                for i, repo in enumerate(self._config.repos):
                    self._log_view.append_log(f"  {repo.url} → {repo.target_path}")
                    step_progress = 0.65 + (i / len(self._config.repos)) * 0.15
                    self._log_view.set_progress(step_progress, f"Cloning {repo.name}...")

                    success = await self._git_ops.sync_repository(
                        repo,
                        progress_callback=lambda msg, p: (
                            self._log_view.append_log(f"    {msg}") if p == 0.1 else None
                        ),
                    )
                    status = "DONE" if success else "FAILED"
                    self._log_view.append_log(f"  [{status}] {repo.url}")
            else:
                self._log_view.append_log("⚠️ No repositories added.")

            # 5. Phase 5 & 6: HypeSync (Applying host-first state)
            if self._config.sync_dotfiles and self._config.dotfiles_url:
                self._log_view.set_progress(0.8, "Synchronizing host state...")
                self._log_view.append_log("🔗 HypeSync: Applying personal dotfiles to host...")
                success = await self._sync_manager.sync_dotfiles(self._config.dotfiles_url)
                status = "DONE" if success else "FAILED"
                self._log_view.append_log(f"  [{status}] Host state synchronized.")

            # 6. Phase 5: Create Isolated Stacks
            if self._config.selected_stacks:
                self._log_view.set_progress(0.85, "Creating isolated environments...")
                self._log_view.append_log(
                    f"🐳 Creating {len(self._config.selected_stacks)} isolated environments..."
                )
                for _i, stack_name in enumerate(self._config.selected_stacks):
                    # Find stack template by name
                    template = next(
                        (
                            s
                            for s in self._stack_manager.get_available_stacks()
                            if s.name == stack_name
                        ),
                        None,
                    )
                    if template:
                        self._log_view.append_log(f"  Building {template.name}...")
                        stack_handle = self._config.stack_names.get(template.id, template.id)

                        try:
                            success = await self._stack_manager.instantiate_stack(
                                template.id,
                                container_name=stack_handle,
                                use_distrobox=self._config.use_distrobox,
                            )
                        except Exception as e:
                            self._log_view.append_log(f"  [ERROR] Stack creation failed: {e}")
                            # Rollback: Clean up partial container
                            self._log_view.append_log(
                                f"  [ROLLBACK] Removing partial container {stack_handle}..."
                            )
                            await self._executor.run_async(["distrobox", "rm", "-f", stack_handle])
                            success = False

                        status = "DONE" if success else "FAILED"
                        self._log_view.append_log(f"  [{status}] {template.name} ready.")

            # 7. Phase 5: HypeSync (Bridging secrets and applying state to containers)
            if self._config.sync_secrets or self._config.sync_ssh_keys:
                self._log_view.set_progress(0.95, "Bridging secrets...")
                self._log_view.append_log("🔐 HypeSync: Bridging secrets and SSH identity...")

                # Build secret config from UI whitelists
                from core.setup.sync_manager import SecretConfig

                secret_config = SecretConfig(
                    inject_ssh_keys=self._config.sync_ssh_keys,
                    inject_github_token=self._config.sync_secrets,
                    inject_git_credentials=True,
                    ssh_key_whitelist=self._config.ssh_key_whitelist,
                    token_whitelist=self._config.token_whitelist,
                )

                await self._sync_manager.inject_secrets(config=secret_config)
                for stack_name in self._config.selected_stacks:
                    template = next(
                        (
                            s
                            for s in self._stack_manager.get_available_stacks()
                            if s.name == stack_name
                        ),
                        None,
                    )
                    if template:
                        await self._sync_manager.inject_secrets(template.id, config=secret_config)
                self._log_view.append_log("  [DONE] Secrets bridged securely.")

            self._log_view.set_progress(1.0, "Setup complete!")
            self._log_view.append_log("-" * 40)
            self._log_view.append_log("\n✨ *** Setup Completed Successfully! ***")
            self._log_view.append_log(
                "Note: Some changes like shell aliases may require a new terminal session."
            )

            # Post-completion actions
            action_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            action_box.set_halign(Gtk.Align.CENTER)
            action_box.set_margin_top(12)

            open_folder_btn = Gtk.Button(label="Open Dev Folder")
            open_folder_btn.connect("clicked", self._on_open_folder_clicked)
            action_box.append(open_folder_btn)

            open_term_btn = Gtk.Button(label="Open in Terminal")
            open_term_btn.connect("clicked", self._on_open_terminal_clicked)
            action_box.append(open_term_btn)

            parent = self._log_view.get_child()
            if isinstance(parent, Gtk.Box):
                parent.append(action_box)

            self._nav_btn.set_label("Finish")
            self._nav_btn.remove_css_class("destructive-action")
            self._nav_btn.add_css_class("suggested-action")

            # Final success feedback
            from ui.toast_manager import ToastManager
            from ui.window import HypeDevHomeWindow

            win = self.get_root()
            if isinstance(win, HypeDevHomeWindow):
                ToastManager.get(win).show_toast(
                    "Machine setup completed successfully!", ntype="success"
                )

        except asyncio.CancelledError:
            self._log_view.set_progress(0.0, "Setup cancelled.")
            self._log_view.append_log("\n❌ Setup process was interrupted.")
        except Exception as e:
            self._log_view.append_log(f"\n‼️ Fatal Error: {e!s}")
            from ui.toast_manager import ToastManager
            from ui.window import HypeDevHomeWindow

            win = self.get_root()
            if isinstance(win, HypeDevHomeWindow):
                ToastManager.get(win).show_toast(f"Setup failed: {e!s}", ntype="error")
