"""HypeDevHome — Machine Setup Step Views."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from app import HypeDevHomeApp

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from core.setup.models import AppInfo, RepoInfo, SetupConfig  # noqa: E402


class AppSelectionView(Adw.Bin):
    """View for selecting applications to install."""

    def __init__(self, apps: list[AppInfo]) -> None:
        super().__init__()
        self._apps = apps

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        step = Gtk.Label(label="Step 1 — Applications")
        step.add_css_class("caption")
        step.add_css_class("dim-label")
        step.set_halign(Gtk.Align.START)
        box.append(step)

        # Header
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header = Gtk.Label(label="Choose what to install")
        header.add_css_class("title-2")
        header.set_hexpand(True)
        header.set_halign(Gtk.Align.START)
        header_box.append(header)

        select_all_btn = Gtk.Button(label="Select All")
        select_all_btn.add_css_class("flat")
        select_all_btn.connect("clicked", self._on_select_all_clicked, True)
        header_box.append(select_all_btn)

        select_none_btn = Gtk.Button(label="Select None")
        select_none_btn.add_css_class("flat")
        select_none_btn.connect("clicked", self._on_select_all_clicked, False)
        header_box.append(select_none_btn)

        box.append(header_box)

        desc = Gtk.Label(
            label=(
                "Toggle apps you want on this machine. "
                "The catalog loads from the package backend (dnf / flatpak, etc.). "
                "Leave all off if you only want repos or config — nothing installs until you run the final step."
            )
        )
        desc.set_wrap(True)
        desc.add_css_class("dim-label")
        box.append(desc)

        # Search
        self._search_entry = Gtk.SearchEntry(placeholder_text="Search applications...")
        self._search_entry.connect("search-changed", self._on_search_changed)
        box.append(self._search_entry)

        # List
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.set_filter_func(self._filter_apps)

        self._update_list()

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._list_box)
        box.append(scrolled)

        self.set_child(box)

    def _update_list(self) -> None:
        """Clear and rebuild the list box rows."""
        child = self._list_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._list_box.remove(child)
            child = next_child

        for app in self._apps:
            row = Adw.ActionRow(title=app.name, subtitle=app.description)
            row.set_icon_name(app.icon)

            switch = Gtk.Switch()
            switch.set_active(app.selected)
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect("notify::active", self._on_switch_toggled, app)

            row.add_suffix(switch)
            # Store app object on row for filtering
            row.app_info = app  # type: ignore
            self._list_box.append(row)

    def _on_switch_toggled(self, switch: Gtk.Switch, _pspec: Any, app: AppInfo) -> None:
        app.selected = switch.get_active()

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self._list_box.invalidate_filter()

    def _filter_apps(self, row: Gtk.ListBoxRow) -> bool:
        search_text = self._search_entry.get_text().lower()
        if not search_text:
            return True

        # In GTK4, when we append a widget to a ListBox, it's wrapped in a ListBoxRow
        action_row = cast(Adw.ActionRow, row.get_child())
        app = getattr(action_row, "app_info", None)
        if not app:
            return True

        return search_text in app.name.lower() or search_text in app.description.lower()

    def _on_select_all_clicked(self, _btn: Gtk.Button, select: bool) -> None:
        for app in self._apps:
            app.selected = select
        self._update_list()

    def update_apps(self, apps: list[AppInfo]) -> None:
        """Update the list of apps dynamically."""
        self._apps = apps
        self._update_list()


class RepoEntryView(Adw.Bin):
    """View for adding repositories to clone."""

    def __init__(self, repos: list[RepoInfo]) -> None:
        super().__init__()
        self._repos = repos

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        step = Gtk.Label(label="Step 2 — Repositories")
        step.add_css_class("caption")
        step.add_css_class("dim-label")
        step.set_halign(Gtk.Align.START)
        box.append(step)

        header = Gtk.Label(label="Clone git repositories")
        header.add_css_class("title-2")
        box.append(header)

        desc = Gtk.Label(
            label=(
                "Paste a URL; clones go under the path shown on each row (default ~/Dev/…). "
                "Skip this step if you already have projects elsewhere."
            )
        )
        desc.set_wrap(True)
        desc.add_css_class("dim-label")
        box.append(desc)

        # Entry area
        entry_box = Gtk.Box(spacing=8)
        self._entry = Gtk.Entry(
            placeholder_text="e.g. https://github.com/you/project.git or git@github.com:you/project.git"
        )
        self._entry.set_hexpand(True)

        add_btn = Gtk.Button(label="Add")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", self._on_add_clicked)

        entry_box.append(self._entry)
        entry_box.append(add_btn)
        box.append(entry_box)

        # List
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._list_box)
        box.append(scrolled)

        self.set_child(box)

    def _on_add_clicked(self, _btn: Gtk.Button) -> None:
        url = self._entry.get_text().strip()
        if not url:
            return

        name = url.split("/")[-1].replace(".git", "")
        repo = RepoInfo(url=url, target_path=f"~/Dev/{name}", name=name)
        self._repos.append(repo)

        row = Adw.ActionRow(title=name, subtitle=url)
        row.set_icon_name("folder-gh-symbolic")
        self._list_box.append(row)

        self._entry.set_text("")


class ExecutionLogView(Adw.Bin):
    """Real-time log output for the setup process."""

    def __init__(self) -> None:
        super().__init__()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)

        step = Gtk.Label(label="Step 6 — Installation log")
        step.add_css_class("caption")
        step.add_css_class("dim-label")
        step.set_halign(Gtk.Align.START)
        box.append(step)

        # Progress Section
        progress_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        progress_box.set_margin_bottom(12)

        self._status_label = Gtk.Label(label="Ready to start...")
        self._status_label.set_halign(Gtk.Align.START)
        self._status_label.add_css_class("heading")
        progress_box.append(self._status_label)

        self._progress_bar = Gtk.ProgressBar()
        self._progress_bar.set_fraction(0.0)
        self._progress_bar.set_hexpand(True)
        progress_box.append(self._progress_bar)

        box.append(progress_box)

        hint = Gtk.Label(
            label="Commands run here. When finished, read the summary; restart the terminal if aliases changed."
        )
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        box.append(hint)

        self._text_view = Gtk.TextView()
        self._text_view.set_editable(False)
        self._text_view.set_monospace(True)
        self._text_view.add_css_class("card")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._text_view)
        box.append(scrolled)

        self.set_child(box)

        buf = self._text_view.get_buffer()
        self._scroll_mark = buf.create_mark("log-end", buf.get_end_iter(), False)

    def set_progress(self, fraction: float, status: str | None = None) -> None:
        """Update the progress bar and status label."""
        self._progress_bar.set_fraction(fraction)
        if status:
            self._status_label.set_label(status)

    def add_completion_widget(self, widget: Gtk.Widget) -> None:
        """Add a widget (e.g. action buttons) to the end of the view."""
        child = self.get_child()
        if isinstance(child, Gtk.Box):
            child.append(widget)

    def append_log(self, text: str) -> None:
        buffer = self._text_view.get_buffer()
        end = buffer.get_end_iter()
        buffer.insert(end, text + "\n")
        buffer.move_mark(self._scroll_mark, buffer.get_end_iter())
        self._text_view.scroll_to_mark(self._scroll_mark, 0.0, False, 0.0, 0.0)


class ConfigurationView(Adw.Bin):
    """View for configuring Git and system settings with previews and backup."""

    def __init__(self, config: SetupConfig, backup_manager=None, settings_applier=None) -> None:
        super().__init__()
        self._config = config
        self._backup_manager = backup_manager
        self._settings_applier = settings_applier

        # Settings state
        self._apply_git = True
        self._apply_aliases = True
        self._apply_hidden_files = True
        self._apply_file_extensions = True
        self._apply_ssh_agent = config.setup_ssh_agent
        self._apply_env_vars = False

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        step = Gtk.Label(label="Step 5 — Configuration")
        step.add_css_class("caption")
        step.add_css_class("dim-label")
        step.set_halign(Gtk.Align.START)
        box.append(step)

        header = Gtk.Label(label="Git, dev folder, and desktop options")
        header.add_css_class("title-2")
        box.append(header)

        desc = Gtk.Label(
            label=(
                "Development folder is where new clones go. "
                "Git name and email are filled from `git config --global` when empty — change any field. "
                "Toggles control file-manager and shell extras applied at the end."
            )
        )
        desc.set_wrap(True)
        desc.add_css_class("dim-label")
        box.append(desc)

        # Settings Group
        group = Adw.PreferencesGroup()
        box.append(group)

        # Dev Folder
        self._dev_folder_row = Adw.EntryRow(title="Development Folder")
        self._dev_folder_row.set_text(config.dev_folder)
        self._dev_folder_row.connect("apply", self._on_dev_folder_changed)
        group.add(self._dev_folder_row)

        # Git Name
        self._git_name_row = Adw.EntryRow(title="Git User Name")
        if config.git_user_name:
            self._git_name_row.set_text(config.git_user_name)
        elif config.setup_git:
            # Maybe detect from host later?
            pass
        self._git_name_row.connect("apply", self._on_git_name_changed)
        group.add(self._git_name_row)

        # Git Email
        self._git_email_row = Adw.EntryRow(title="Git User Email")
        if config.git_user_email:
            self._git_email_row.set_text(config.git_user_email)
        self._git_email_row.connect("apply", self._on_git_email_changed)
        group.add(self._git_email_row)

        # Git Editor
        self._git_editor_row = Adw.EntryRow(title="Git Editor (optional)")
        self._git_editor_row.set_text("")
        self._git_editor_row.connect("apply", self._on_git_editor_changed)
        group.add(self._git_editor_row)

        # Settings toggles
        settings_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        # SSH Agent Toggle
        ssh_row = Adw.ActionRow(
            title="Auto-start SSH Agent", subtitle="Ensures ssh-agent is running on login"
        )
        self._ssh_switch = Gtk.Switch()
        self._ssh_switch.set_active(config.setup_ssh_agent)
        self._ssh_switch.set_valign(Gtk.Align.CENTER)
        self._ssh_switch.connect("notify::active", self._on_ssh_toggled)
        ssh_row.add_suffix(self._ssh_switch)
        settings_box.append(ssh_row)

        # Btrfs Toggle
        btrfs_row = Adw.ActionRow(
            title="Use Btrfs Subvolumes", subtitle="Enable optimizations if dev folder is on Btrfs"
        )
        self._btrfs_switch = Gtk.Switch()
        self._btrfs_switch.set_active(config.btrfs_subvolume)
        self._btrfs_switch.set_valign(Gtk.Align.CENTER)
        self._btrfs_switch.connect("notify::active", self._on_btrfs_toggled)
        btrfs_row.add_suffix(self._btrfs_switch)
        settings_box.append(btrfs_row)

        # Show hidden files toggle
        hidden_files_row = Adw.ActionRow(
            title="Show Hidden Files", subtitle="Configure file manager to show dotfiles"
        )
        self._hidden_files_switch = Gtk.Switch()
        self._hidden_files_switch.set_active(True)
        self._hidden_files_switch.set_valign(Gtk.Align.CENTER)
        self._hidden_files_switch.connect("notify::active", self._on_hidden_files_toggled)
        hidden_files_row.add_suffix(self._hidden_files_switch)
        settings_box.append(hidden_files_row)

        # Show file extensions toggle
        file_ext_row = Adw.ActionRow(
            title="Show File Extensions", subtitle="Display file extensions in file manager"
        )
        self._file_ext_switch = Gtk.Switch()
        self._file_ext_switch.set_active(True)
        self._file_ext_switch.set_valign(Gtk.Align.CENTER)
        self._file_ext_switch.connect("notify::active", self._on_file_ext_toggled)
        file_ext_row.add_suffix(self._file_ext_switch)
        settings_box.append(file_ext_row)

        # Shell aliases toggle
        aliases_row = Adw.ActionRow(
            title="Apply Shell Aliases", subtitle="Add git shortcuts and modern tool aliases"
        )
        self._aliases_switch = Gtk.Switch()
        self._aliases_switch.set_active(True)
        self._aliases_switch.set_valign(Gtk.Align.CENTER)
        self._aliases_switch.connect("notify::active", self._on_aliases_toggled)
        aliases_row.add_suffix(self._aliases_switch)
        settings_box.append(aliases_row)

        group.add(settings_box)

        # Action buttons
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        button_box.set_halign(Gtk.Align.END)
        button_box.set_margin_top(12)

        # Preview button
        self._preview_btn = Gtk.Button(label="Preview Changes")
        self._preview_btn.connect("clicked", self._on_preview_clicked)
        button_box.append(self._preview_btn)

        # Backup button
        self._backup_btn = Gtk.Button(label="Backup Config")
        self._backup_btn.add_css_class("outlined")
        self._backup_btn.connect("clicked", self._on_backup_clicked)
        button_box.append(self._backup_btn)

        # Restore button
        self._restore_btn = Gtk.Button(label="Restore")
        self._restore_btn.add_css_class("outlined")
        self._restore_btn.connect("clicked", self._on_restore_clicked)
        button_box.append(self._restore_btn)

        box.append(button_box)

        # Summary Group (Phase 5 refinement)
        summary_group = Adw.PreferencesGroup(title="Final Summary")
        box.append(summary_group)
        self._summary_label = Gtk.Label(label="Select 'Next' to review setup summary...")
        self._summary_label.set_margin_top(12)
        self._summary_label.add_css_class("dim-label")
        summary_group.add(self._summary_label)

        self.set_child(box)

    def update_summary(self, summary_text: str) -> None:
        """Update the final setup summary."""
        self._summary_label.set_label(summary_text)
        self._summary_label.remove_css_class("dim-label")

    def _on_dev_folder_changed(self, entry: Adw.EntryRow) -> None:
        self._config.dev_folder = entry.get_text()

    def _on_git_name_changed(self, entry: Adw.EntryRow) -> None:
        self._config.git_user_name = entry.get_text()

    def _on_git_email_changed(self, entry: Adw.EntryRow) -> None:
        self._config.git_user_email = entry.get_text()

    def _on_git_editor_changed(self, entry: Adw.EntryRow) -> None:
        self._config.env_vars["GIT_EDITOR"] = entry.get_text()

    def _on_ssh_toggled(self, switch: Gtk.Switch, _pspec: Any) -> None:
        self._config.setup_ssh_agent = switch.get_active()
        self._apply_ssh_agent = switch.get_active()

    def _on_btrfs_toggled(self, switch: Gtk.Switch, _pspec: Any) -> None:
        self._config.btrfs_subvolume = switch.get_active()

    def _on_hidden_files_toggled(self, switch: Gtk.Switch, _pspec: Any) -> None:
        self._apply_hidden_files = switch.get_active()

    def _on_file_ext_toggled(self, switch: Gtk.Switch, _pspec: Any) -> None:
        self._apply_file_extensions = switch.get_active()

    def _on_aliases_toggled(self, switch: Gtk.Switch, _pspec: Any) -> None:
        self._apply_aliases = switch.get_active()

    def _on_preview_clicked(self, _btn: Gtk.Button) -> None:
        """Show preview logic."""
        # For Phase 4, we'll just log that we are calculating previews
        print("Calculating configuration preview...")

    def _on_backup_clicked(self, _btn: Gtk.Button) -> None:
        """Trigger backup using Agent C backup manager."""
        if self._backup_manager:
            app = cast("HypeDevHomeApp", Gio.Application.get_default())
            if app:
                self._backup_task = app.enqueue_task(self._run_backup())

    async def _run_backup(self) -> None:
        GLib.idle_add(self._backup_btn.set_sensitive, False)
        GLib.idle_add(self._backup_btn.set_label, "Backing up...")
        await self._backup_manager.create_backup("Manual user backup")
        GLib.idle_add(self._backup_btn.set_label, "Backup Config")
        GLib.idle_add(self._backup_btn.set_sensitive, True)

    def _on_restore_clicked(self, _btn: Gtk.Button) -> None:
        """Show restore logic."""
        if self._backup_manager:
            # We would show a dialog here, but for integration we'll just log
            print("Restore requested")

    def sync_config(self) -> None:
        """Force sync entries that might not have triggered 'apply'."""
        self._config.dev_folder = self._dev_folder_row.get_text()
        self._config.git_user_name = self._git_name_row.get_text()
        self._config.git_user_email = self._git_email_row.get_text()

    def apply_prefill_to_rows(self) -> None:
        """Push SetupConfig values into entry rows after async host detection."""
        if self._config.dev_folder:
            self._dev_folder_row.set_text(self._config.dev_folder)
        if self._config.git_user_name:
            self._git_name_row.set_text(self._config.git_user_name)
        if self._config.git_user_email:
            self._git_email_row.set_text(self._config.git_user_email)

    def get_settings_config(self) -> dict:
        """Get the current settings as a dict for DevSettingsApplier."""
        return {
            "git_name": self._config.git_user_name,
            "git_email": self._config.git_user_email,
            "git_editor": self._git_editor_row.get_text(),
            "enable_aliases": self._apply_aliases,
            "enable_hidden_files": self._apply_hidden_files,
            "enable_file_extensions": self._apply_file_extensions,
            "enable_ssh_agent": self._apply_ssh_agent,
        }


class EnvironmentSelectionView(Adw.Bin):
    """View for selecting isolated stacks (Distrobox/Toolbx)."""

    def __init__(self, config: SetupConfig) -> None:
        super().__init__()
        self._config = config

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        step = Gtk.Label(label="Step 3 — Environments")
        step.add_css_class("caption")
        step.add_css_class("dim-label")
        step.set_halign(Gtk.Align.START)
        box.append(step)

        header = Gtk.Label(label="Optional container stacks")
        header.add_css_class("title-2")
        box.append(header)

        desc = Gtk.Label(
            label=(
                "Pick Distrobox or Toolbx, then enable template stacks you want created later. "
                "Requires a working container engine. Skip if you develop only on the host."
            )
        )
        desc.set_wrap(True)
        desc.add_css_class("dim-label")
        box.append(desc)

        # Platform choice
        platform_group = Adw.PreferencesGroup(title="Platform")
        box.append(platform_group)

        self._dbx_row = Adw.ActionRow(
            title="Distrobox (Recommended)", subtitle="Seamless host integration and app exporting"
        )
        self._dbx_check = Gtk.CheckButton()
        self._dbx_check.set_active(config.use_distrobox)
        self._dbx_check.set_valign(Gtk.Align.CENTER)
        self._dbx_check.connect("toggled", self._on_platform_toggled, True)
        self._dbx_row.add_prefix(self._dbx_check)
        platform_group.add(self._dbx_row)

        self._tbx_row = Adw.ActionRow(
            title="Toolbx", subtitle="Native OCI containers for immutable systems"
        )
        self._tbx_check = Gtk.CheckButton()
        self._tbx_check.set_group(self._dbx_check)
        self._tbx_check.set_active(not config.use_distrobox)
        self._tbx_check.set_valign(Gtk.Align.CENTER)
        self._tbx_check.connect("toggled", self._on_platform_toggled, False)
        self._tbx_row.add_prefix(self._tbx_check)
        platform_group.add(self._tbx_row)

        # Stacks List
        stacks_group = Adw.PreferencesGroup(title="Available Stacks")
        box.append(stacks_group)

        # Mock stacks for now
        self._stacks = [
            ("Python Data Science", "Jupyter, Pandas, Scikit-learn", "python-symbolic"),
            ("Node.js Web Dev", "Node 20, Yarn, TypeScript", "web-browser-symbolic"),
            ("Rust Backend", "Cargo, Rustup, Clippy", "system-run-symbolic"),
            ("Go Services", "GOPATH setup, Air hot-reload", "application-x-executable-symbolic"),
        ]

        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        for name, description, icon in self._stacks:
            row = Adw.ActionRow(title=name, subtitle=description, icon_name=icon)

            # Custom name entry
            name_entry = Gtk.Entry(placeholder_text=f"e.g. {name.lower().replace(' ', '-')}")
            name_entry.set_valign(Gtk.Align.CENTER)
            name_entry.set_visible(name in config.selected_stacks)
            name_entry.set_text(config.stack_names.get(name, ""))
            name_entry.connect("changed", self._on_name_changed, name)

            switch = Gtk.Switch()
            switch.set_active(name in config.selected_stacks)
            switch.set_valign(Gtk.Align.CENTER)
            switch.connect("notify::active", self._on_stack_toggled, name, name_entry)

            row.add_suffix(name_entry)
            row.add_suffix(switch)
            self._list_box.append(row)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(self._list_box)
        box.append(scrolled)

        self.set_child(box)

    def _on_platform_toggled(self, _check: Gtk.CheckButton, is_dbx: bool) -> None:
        self._config.use_distrobox = is_dbx

    def _on_stack_toggled(
        self, switch: Gtk.Switch, _pspec: Any, name: str, entry: Gtk.Entry
    ) -> None:
        active = switch.get_active()
        entry.set_visible(active)
        if active:
            if name not in self._config.selected_stacks:
                self._config.selected_stacks.append(name)
        else:
            if name in self._config.selected_stacks:
                self._config.selected_stacks.remove(name)

    def _on_name_changed(self, entry: Gtk.Entry, template_id: str) -> None:
        name = entry.get_text().strip()
        # Regex for valid container names
        is_valid = bool(re.match(r"^[a-z0-9](-?[a-z0-9])*$", name)) if name else True
        if not is_valid:
            entry.add_css_class("error")
            entry.set_tooltip_text("Invalid name. Use lowercase, numbers, and hyphens.")
        else:
            entry.remove_css_class("error")
            entry.set_tooltip_text(None)
            if name:
                self._config.stack_names[template_id] = name
            elif template_id in self._config.stack_names:
                del self._config.stack_names[template_id]


class SyncConfigurationView(Adw.Bin):
    """View for configuring personal state and secrets sync."""

    def __init__(self, config: SetupConfig) -> None:
        super().__init__()
        self._config = config

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        step = Gtk.Label(label="Step 4 — Sync")
        step.add_css_class("caption")
        step.add_css_class("dim-label")
        step.set_halign(Gtk.Align.START)
        box.append(step)

        header = Gtk.Label(label="Dotfiles and secrets (optional)")
        header.add_css_class("title-2")
        box.append(header)

        sync_desc = Gtk.Label(
            label=(
                "If you use HypeSync-style dotfiles, enter a repo URL. "
                "Secrets bridging is advanced — leave off unless you know you need it."
            )
        )
        sync_desc.set_wrap(True)
        sync_desc.add_css_class("dim-label")
        box.append(sync_desc)

        # Dotfiles Group
        dotfiles_group = Adw.PreferencesGroup(title="Dotfiles Synchronization")
        box.append(dotfiles_group)

        self._sync_switch_row = Adw.ActionRow(
            title="Enable Dotfiles Sync",
            subtitle="Automatically apply your personal configurations and aliases",
        )
        self._sync_switch = Gtk.Switch()
        self._sync_switch.set_active(config.sync_dotfiles)
        self._sync_switch.set_valign(Gtk.Align.CENTER)
        self._sync_switch.connect("notify::active", self._on_sync_toggled)
        self._sync_switch_row.add_suffix(self._sync_switch)
        dotfiles_group.add(self._sync_switch_row)

        self._repo_row = Adw.EntryRow(title="Dotfiles Repository URL")
        self._repo_row.set_text(config.dotfiles_url or "")
        self._repo_row.set_sensitive(config.sync_dotfiles)
        self._repo_row.connect("apply", self._on_repo_changed)
        dotfiles_group.add(self._repo_row)

        # Secrets Group (Granular Whitelist)
        secrets_group = Adw.PreferencesGroup(title="Secrets and identity whitelist")
        box.append(secrets_group)

        # SSH Keys Checkbox
        self._ssh_row = Adw.ActionRow(
            title="SSH Identity", subtitle="Bridge host SSH keys available in containers"
        )
        self._ssh_check = Gtk.CheckButton(label="Bridge SSH Keys")
        self._ssh_check.set_active(config.sync_ssh_keys)
        self._ssh_check.set_valign(Gtk.Align.CENTER)
        self._ssh_check.connect("toggled", self._on_ssh_toggled)
        self._ssh_row.add_suffix(self._ssh_check)
        secrets_group.add(self._ssh_row)

        self._ssh_whitelist_row = Adw.ActionRow(
            title="Key Whitelist", subtitle="id_rsa, id_ed25519"
        )
        secrets_group.add(self._ssh_whitelist_row)

        # Git Config Checkbox
        self._git_row = Adw.ActionRow(
            title="Git Identity", subtitle="Sync global .gitconfig (Name/Email)"
        )
        self._git_check = Gtk.CheckButton(label="Sync Git Config")
        self._git_check.set_active(True)
        self._git_check.set_valign(Gtk.Align.CENTER)
        self._git_row.add_suffix(self._git_check)
        secrets_group.add(self._git_row)

        # API Tokens Checkbox
        self._token_row = Adw.ActionRow(
            title="GitHub API Tokens", subtitle="Bridge authentication secrets securely"
        )
        self._token_check = Gtk.CheckButton(label="Sync API Tokens")
        self._token_check.set_active(config.sync_secrets)
        self._token_check.set_valign(Gtk.Align.CENTER)
        self._token_check.connect("toggled", self._on_secrets_toggled)
        self._token_row.add_suffix(self._token_check)
        secrets_group.add(self._token_row)

        self._token_whitelist_row = Adw.ActionRow(title="Token Whitelist", subtitle="GITHUB_TOKEN")
        secrets_group.add(self._token_whitelist_row)

        self.set_child(box)

    def _on_sync_toggled(self, switch: Gtk.Switch, _pspec: Any) -> None:
        active = switch.get_active()
        self._config.sync_dotfiles = active
        self._repo_row.set_sensitive(active)

    def _on_repo_changed(self, entry: Adw.EntryRow) -> None:
        self._config.dotfiles_url = entry.get_text()

    def _on_secrets_toggled(self, check: Gtk.CheckButton) -> None:
        active = check.get_active()
        self._config.sync_secrets = active
        if active:
            if "GITHUB_TOKEN" not in self._config.token_whitelist:
                self._config.token_whitelist.append("GITHUB_TOKEN")
        else:
            self._config.token_whitelist = [
                t for t in self._config.token_whitelist if t != "GITHUB_TOKEN"
            ]

    def _on_ssh_toggled(self, check: Gtk.CheckButton) -> None:
        active = check.get_active()
        self._config.sync_ssh_keys = active
        if active:
            for key in ["id_rsa", "id_ed25519"]:
                if key not in self._config.ssh_key_whitelist:
                    self._config.ssh_key_whitelist.append(key)
        else:
            self._config.ssh_key_whitelist = [
                k for k in self._config.ssh_key_whitelist if k not in ["id_rsa", "id_ed25519"]
            ]

    def sync_config(self) -> None:
        """Sync text entries and finalize whitelists."""
        self._config.dotfiles_url = self._repo_row.get_text()
