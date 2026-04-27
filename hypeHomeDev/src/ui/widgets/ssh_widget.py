"""HypeDevHome — SSH keychain widget.

Displays loaded SSH keys from ssh-agent with
fingerprints and quick actions.
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from ui.widgets.dashboard_widget import DashboardWidget  # noqa: E402
from ui.widgets.empty_state import EmptyState  # noqa: E402
from ui.widgets.error_banner import ErrorBanner  # noqa: E402

log = logging.getLogger(__name__)


class SSHKey:
    """Represents a loaded SSH key."""

    def __init__(self, fingerprint: str, comment: str = "", key_path: str = "") -> None:
        self.fingerprint = fingerprint
        self.comment = comment
        self.key_path = key_path

    def __str__(self) -> str:
        return f"SSHKey({self.fingerprint[:16]}..., {self.comment})"


class SSHWidget(DashboardWidget):
    """SSH keychain widget showing loaded keys in ssh-agent.

    Allows adding/removing keys and shows agent status.
    """

    # Metadata for widget gallery
    widget_title = "SSH Keys"
    widget_icon = "key-symbolic"
    widget_description = "Monitor and manage SSH keys loaded in ssh-agent"
    widget_category = "System"

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the SSH widget."""
        # Initialize data before super().__init__ because it calls build_ui()
        self._keys: list[SSHKey] = []
        self._agent_available: bool = False
        self._agent_socket: str = ""
        self._monitor_thread: threading.Thread | None = None
        self._stop_monitor = threading.Event()
        self._last_agent_check: float = 0
        self._agent_check_interval: float = 5.0  # seconds
        self._error_banner: ErrorBanner | None = None
        self._empty_state: EmptyState | None = None

        super().__init__(
            widget_id="ssh",
            title=self.widget_title,
            icon_name=self.widget_icon,
            **kwargs,
        )

    def build_ui(self) -> None:
        """Build the SSH widget's specific UI."""
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)
        vbox.set_margin_bottom(8)

        # Error banner (initially hidden)
        self._error_banner = ErrorBanner(message="")
        self._error_banner.hide()
        vbox.append(self._error_banner)

        # Status row
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._status_icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        self._status_icon.set_pixel_size(16)
        status_row.append(self._status_icon)

        self._status_label = Gtk.Label(label="Checking SSH agent...")
        self._status_label.set_halign(Gtk.Align.START)
        status_row.append(self._status_label)

        # Spacer
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        status_row.append(spacer)

        # Refresh button
        self._refresh_btn = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
        self._refresh_btn.set_has_frame(False)
        self._refresh_btn.set_tooltip_text("Refresh")
        self._refresh_btn.connect("clicked", self._on_refresh_clicked)
        status_row.append(self._refresh_btn)

        # Settings button
        self._settings_btn = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        self._settings_btn.set_has_frame(False)
        self._settings_btn.set_tooltip_text("Settings")
        self._settings_btn.connect("clicked", self._on_settings_clicked)
        status_row.append(self._settings_btn)

        vbox.append(status_row)

        # Keys list container
        self._list_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._list_container.set_vexpand(True)

        # Empty state (initially hidden)
        self._empty_state = EmptyState(
            icon_name="key-symbolic",
            title="No SSH keys loaded",
            description="Add SSH keys to ssh-agent to see them here",
            button_label="Add Key",
            button_action=self._on_add_clicked,
        )
        self._empty_state.hide()
        self._list_container.append(self._empty_state)

        # Keys list
        self._list_box = Gtk.ListBox()
        self._list_box.add_css_class("boxed-list")
        self._list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._list_box.connect("row-selected", self._on_key_selected)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_min_content_height(120)
        scrolled.set_child(self._list_box)
        self._list_container.append(scrolled)

        vbox.append(self._list_container)

        # Action buttons
        button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self._add_btn = Gtk.Button.new_with_label("Add Key")
        self._add_btn.set_icon_name("list-add-symbolic")
        self._add_btn.connect("clicked", self._on_add_clicked)
        button_row.append(self._add_btn)

        self._remove_btn = Gtk.Button.new_with_label("Remove Selected")
        self._remove_btn.set_icon_name("list-remove-symbolic")
        self._remove_btn.set_sensitive(False)
        self._remove_btn.connect("clicked", self._on_remove_clicked)
        button_row.append(self._remove_btn)

        vbox.append(button_row)

        self.append(vbox)

    def on_activate(self) -> None:
        """Called when the widget is shown on the dashboard."""
        super().on_activate()
        # Initial check
        GLib.idle_add(self._check_agent)
        # Start background monitoring
        self._start_agent_monitor()

    def on_deactivate(self) -> None:
        """Called when the widget is removed or app closes."""
        super().on_deactivate()
        # Stop background monitoring
        self._stop_agent_monitor()

    def refresh(self) -> bool:
        """Periodic refresh called by the parent DashboardWidget."""
        current_time = time.time()
        if current_time - self._last_agent_check >= self._agent_check_interval:
            self._last_agent_check = current_time
            GLib.idle_add(self._check_agent)
        return True

    def _start_agent_monitor(self) -> None:
        """Start background thread to monitor ssh-agent availability."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._stop_monitor.clear()
        self._monitor_thread = threading.Thread(
            target=self._agent_monitor_loop, name="SSHAgentMonitor", daemon=True
        )
        self._monitor_thread.start()
        log.debug("SSH agent monitor started")

    def _stop_agent_monitor(self) -> None:
        """Stop the background monitoring thread."""
        self._stop_monitor.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
        log.debug("SSH agent monitor stopped")

    def _agent_monitor_loop(self) -> None:
        """Background thread that monitors ssh-agent availability."""
        while not self._stop_monitor.is_set():
            try:
                # Check agent every 2 seconds
                time.sleep(2)
                GLib.idle_add(self._check_agent)
            except Exception as e:
                log.error("Error in agent monitor loop: %s", e)
                time.sleep(5)  # Back off on error

    def _check_agent(self) -> None:
        """Check if ssh-agent is available and load keys."""
        # Check for SSH_AUTH_SOCK environment variable
        self._agent_socket = os.environ.get("SSH_AUTH_SOCK", "")
        socket_exists = bool(self._agent_socket and os.path.exists(self._agent_socket))

        # Check if agent is actually responding
        agent_responding = False
        if socket_exists:
            try:
                result = subprocess.run(
                    ["ssh-add", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    env=os.environ,
                )
                # Return code 0 means success (keys loaded), 1 means no keys, both are valid
                agent_responding = result.returncode in (0, 1)
            except (subprocess.SubprocessError, FileNotFoundError):
                agent_responding = False

        self._agent_available = socket_exists and agent_responding

        if self._agent_available:
            self._status_icon.set_from_icon_name("emblem-ok-symbolic")
            self._status_label.set_label(f"SSH agent available ({len(self._keys)} keys)")
            self._add_btn.set_sensitive(True)
            self._settings_btn.set_sensitive(True)
            self._hide_error_banner()
            self._load_keys()
        else:
            self._status_icon.set_from_icon_name("dialog-error-symbolic")
            if not socket_exists:
                self._status_label.set_label("SSH agent not found")
                self._show_error_banner(
                    "SSH agent not available",
                    "Set SSH_AUTH_SOCK environment variable or start ssh-agent",
                )
            else:
                self._status_label.set_label("SSH agent not responding")
                self._show_error_banner(
                    "SSH agent not responding", "Check if ssh-agent is running and accessible"
                )
            self._add_btn.set_sensitive(False)
            self._settings_btn.set_sensitive(False)
            self._clear_keys_list()

    def _load_keys(self) -> None:
        """Load keys from ssh-agent using ssh-add -l."""
        self._keys.clear()
        try:
            result = subprocess.run(
                ["ssh-add", "-l"],
                capture_output=True,
                text=True,
                timeout=2,
                env=os.environ,  # Pass SSH_AUTH_SOCK
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and not line.startswith("The agent has no identities"):
                        # Parse line like: "4096 SHA256:abc123... comment (RSA)"
                        parts = line.split()
                        if len(parts) >= 3:
                            fingerprint = parts[1]
                            comment = " ".join(parts[2:]) if len(parts) > 3 else ""
                            # Try to get key path (not directly available from ssh-add -l)
                            key_path = self._find_key_path(fingerprint)
                            self._keys.append(SSHKey(fingerprint, comment, key_path))
            elif result.returncode == 1:
                # No keys loaded
                pass
        except (subprocess.SubprocessError, FileNotFoundError):
            log.warning("Failed to run ssh-add")

        self._update_keys_list()

    def _find_key_path(self, fingerprint: str) -> str:
        """Try to find the path of a key by its fingerprint."""
        # This is a best-effort attempt
        # We could search common locations or parse ssh-add -L output
        try:
            result = subprocess.run(
                ["ssh-add", "-L"],
                capture_output=True,
                text=True,
                timeout=2,
                env=os.environ,
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line and fingerprint in line:
                        # Line format: "key-type key-data comment"
                        parts = line.split()
                        if len(parts) >= 3:
                            # The comment might be a path
                            comment = parts[2]
                            if os.path.exists(comment):
                                return comment
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return ""

    def _show_error_banner(self, title: str, message: str) -> None:
        """Show an error banner."""
        if self._error_banner:
            self._error_banner.message = f"{title}: {message}"
            self._error_banner.set_visible(True)

    def _hide_error_banner(self) -> None:
        """Hide the error banner."""
        if self._error_banner:
            self._error_banner.set_visible(False)

    def _update_keys_list(self) -> None:
        """Update the list of keys in the UI."""
        # Clear existing rows
        child = self._list_box.get_first_child()
        while child:
            self._list_box.remove(child)
            child = self._list_box.get_first_child()

        if not self._keys:
            # Show empty state and hide list
            if hasattr(self, "_empty_state") and self._empty_state:
                self._empty_state.set_visible(True)
            self._list_box.set_visible(False)
            self._remove_btn.set_sensitive(False)
            return

        # Hide empty state and show list
        if self._empty_state:
            self._empty_state.set_visible(False)
        self._list_box.set_visible(True)

        for key in self._keys:
            row = Gtk.ListBoxRow()
            row.set_activatable(True)
            row.connect("activate", self._on_key_activated, key)

            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            box.set_margin_top(8)
            box.set_margin_bottom(8)
            box.set_margin_start(12)
            box.set_margin_end(12)

            # Top row: fingerprint and key type
            top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

            # Key type icon
            key_type = self._get_key_type(key.fingerprint)
            key_icon = Gtk.Image.new_from_icon_name(self._get_key_icon(key_type))
            key_icon.set_pixel_size(16)
            top_row.append(key_icon)

            # Fingerprint (truncated)
            fp_short = key.fingerprint
            if len(fp_short) > 32:
                fp_short = fp_short[:16] + "..." + fp_short[-16:]
            fp_label = Gtk.Label(label=fp_short)
            fp_label.set_halign(Gtk.Align.START)
            fp_label.add_css_class("monospace")
            top_row.append(fp_label)

            # Spacer
            spacer = Gtk.Box()
            spacer.set_hexpand(True)
            top_row.append(spacer)

            # Key type label
            type_label = Gtk.Label(label=key_type)
            type_label.set_halign(Gtk.Align.END)
            type_label.add_css_class("dim-label")
            type_label.add_css_class("caption")
            top_row.append(type_label)

            box.append(top_row)

            # Comment/path
            if key.comment:
                comment_label = Gtk.Label(label=key.comment)
                comment_label.set_halign(Gtk.Align.START)
                comment_label.add_css_class("dim-label")
                comment_label.add_css_class("caption")
                box.append(comment_label)
            elif key.key_path:
                path_label = Gtk.Label(label=key.key_path)
                path_label.set_halign(Gtk.Align.START)
                path_label.add_css_class("dim-label")
                path_label.add_css_class("caption")
                box.append(path_label)

            row.set_child(box)
            self._list_box.append(row)

        self._remove_btn.set_sensitive(True)

    def _get_key_type(self, fingerprint: str) -> str:
        """Determine key type from fingerprint."""
        # Check for key type in parentheses
        if "(RSA)" in fingerprint.upper():
            return "RSA"
        elif "(ECDSA)" in fingerprint.upper():
            return "ECDSA"
        elif "(ED25519)" in fingerprint.upper():
            return "Ed25519"
        elif fingerprint.startswith("SHA256:"):
            # Try to get more info from ssh-add -L if available
            return "RSA/ECDSA/Ed25519"
        return "Unknown"

    def _get_key_icon(self, key_type: str) -> str:
        """Get icon name for key type."""
        icons = {
            "RSA": "security-high-symbolic",
            "ECDSA": "security-medium-symbolic",
            "Ed25519": "security-low-symbolic",
            "RSA/ECDSA/Ed25519": "key-symbolic",
        }
        return icons.get(key_type, "key-symbolic")

    def _clear_keys_list(self) -> None:
        """Clear the keys list UI."""
        self._keys.clear()
        self._update_keys_list()

    def _on_refresh_clicked(self, _button: Gtk.Button) -> None:
        """Handle refresh button click."""
        self._check_agent()

    def _on_settings_clicked(self, _button: Gtk.Button) -> None:
        """Handle settings button click."""
        self.show_settings_dialog()

    def _on_key_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        """Handle key selection in the list."""
        self._remove_btn.set_sensitive(row is not None)

    def _on_add_clicked(self, _button: Gtk.Button | None = None) -> None:
        """Handle add key button click."""
        if not self._agent_available:
            self._show_error_banner(
                "SSH agent not available", "Cannot add keys without a running ssh-agent"
            )
            return

        # Create a file chooser dialog
        from typing import cast

        dialog = Gtk.FileChooserDialog(
            title="Select SSH Private Key",
            transient_for=cast(Gtk.Window, self.get_root()),
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            "_Cancel",
            Gtk.ResponseType.CANCEL,
            "_Open",
            Gtk.ResponseType.OK,
        )

        # Filter for private key files
        filter_key = Gtk.FileFilter()
        filter_key.set_name("SSH Private Keys")
        filter_key.add_pattern("id_*")
        filter_key.add_pattern("*.pem")
        filter_key.add_pattern("*.key")
        dialog.add_filter(filter_key)

        # Filter for all files
        filter_all = Gtk.FileFilter()
        filter_all.set_name("All Files")
        filter_all.add_pattern("*")
        dialog.add_filter(filter_all)

        # Set default directory to ~/.ssh
        ssh_dir = os.path.expanduser("~/.ssh")
        if os.path.isdir(ssh_dir):
            dialog.set_current_folder(Gio.File.new_for_path(ssh_dir))

        dialog.connect("response", self._on_file_chooser_response)
        dialog.present()

    def _on_file_chooser_response(self, dialog: Gtk.Dialog, response_id: int) -> None:
        """Handle file chooser dialog response."""
        if response_id == Gtk.ResponseType.OK:
            # We know this is a FileChooserDialog
            from typing import cast

            file_chooser = cast(Gtk.FileChooser, dialog)
            file = file_chooser.get_file()
            if file:
                path = file.get_path()
                if path:
                    self._add_key(path)
        dialog.destroy()

    def _add_key(self, key_path: str) -> None:
        """Add a key to ssh-agent."""
        try:
            result = subprocess.run(
                ["ssh-add", key_path],
                capture_output=True,
                text=True,
                timeout=5,
                env=os.environ,
            )
            if result.returncode == 0:
                log.info("Added key: %s", key_path)
                # Reload keys
                self._load_keys()
            else:
                log.error("Failed to add key: %s", result.stderr)
                # Show error dialog
                self._show_error("Failed to add key", result.stderr)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            log.error("Error adding key: %s", e)
            self._show_error("Error adding key", str(e))

    def _on_remove_clicked(self, _button: Gtk.Button) -> None:
        """Handle remove key button click."""
        # Get selected row
        selected = self._list_box.get_selected_row()
        if selected:
            index = selected.get_index()
            if 0 <= index < len(self._keys):
                key = self._keys[index]
                self._remove_key(key)

    def _on_key_activated(self, _row: Gtk.ListBoxRow, key: SSHKey) -> None:
        """Handle key row activation (click)."""
        # For now, just select the row
        pass

    def _remove_key(self, key: SSHKey) -> None:
        """Remove a key from ssh-agent."""
        try:
            # ssh-add -d requires the fingerprint
            result = subprocess.run(
                ["ssh-add", "-d", key.fingerprint],
                capture_output=True,
                text=True,
                timeout=2,
                env=os.environ,
            )
            if result.returncode == 0:
                log.info("Removed key: %s", key.fingerprint)
                # Reload keys
                self._load_keys()
            else:
                log.error("Failed to remove key: %s", result.stderr)
                # Try alternative method with key file if we have path
                if key.key_path and os.path.exists(key.key_path):
                    self._remove_key_by_path(key.key_path)
                else:
                    self._show_error("Failed to remove key", result.stderr)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            log.error("Error removing key: %s", e)
            self._show_error("Error removing key", str(e))

    def _remove_key_by_path(self, key_path: str) -> None:
        """Remove a key by its file path."""
        try:
            result = subprocess.run(
                ["ssh-add", "-d", key_path],
                capture_output=True,
                text=True,
                timeout=2,
                env=os.environ,
            )
            if result.returncode == 0:
                log.info("Removed key by path: %s", key_path)
                self._load_keys()
            else:
                log.error("Failed to remove key by path: %s", result.stderr)
                self._show_error("Failed to remove key", result.stderr)
        except (subprocess.SubprocessError, FileNotFoundError) as e:
            log.error("Error removing key by path: %s", e)
            self._show_error("Error removing key", str(e))

    def show_settings_dialog(self) -> None:
        """Show settings dialog for SSH widget."""

        dialog = Adw.PreferencesDialog(
            title="SSH Widget Settings",
        )
        # Set transient parent after creation        # Settings dialog in Libadwaita 1.4+ is presented via present(parent)
        root = self.get_root()
        parent = cast(Gtk.Window, root) if isinstance(root, Gtk.Window) else None

        # General page
        page = Adw.PreferencesPage()
        dialog.add(page)

        # Monitoring settings group
        group = Adw.PreferencesGroup(
            title="Monitoring", description="Configure SSH agent monitoring"
        )
        page.add(group)

        # Check interval
        row = Adw.SpinRow(
            title="Check interval",
            subtitle="Seconds between agent checks",
            adjustment=Gtk.Adjustment(
                value=self._agent_check_interval,
                lower=1.0,
                upper=60.0,
                step_increment=1.0,
                page_increment=5.0,
            ),
        )
        row.connect("changed", self._on_check_interval_changed)
        group.add(row)

        # Agent info group
        info_group = Adw.PreferencesGroup(
            title="Agent Information", description="Current SSH agent status"
        )
        page.add(info_group)

        # Agent socket
        socket_row = Adw.ActionRow(
            title="Agent Socket",
            subtitle=self._agent_socket or "Not set",
        )
        info_group.add(socket_row)

        # Key count
        key_count_row = Adw.ActionRow(
            title="Loaded Keys",
            subtitle=str(len(self._keys)),
        )
        info_group.add(key_count_row)

        dialog.present(parent)

    def _on_check_interval_changed(self, spin_row: Adw.SpinRow) -> None:
        """Handle check interval change."""
        self._agent_check_interval = spin_row.get_value()
        log.debug("SSH agent check interval changed to %f seconds", self._agent_check_interval)

    def get_config(self) -> dict[str, Any]:
        """Return the current widget configuration for persistence."""
        config = super().get_config()
        config.update(
            {
                "agent_check_interval": self._agent_check_interval,
            }
        )
        return config

    def _show_error(self, title: str, message: str) -> None:
        """Show an error dialog."""
        from typing import cast

        dialog = Gtk.MessageDialog(
            transient_for=cast(Gtk.Window, self.get_root()),
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
        )
        msg_dialog = cast(Gtk.MessageDialog, dialog)
        from typing import Any

        cast(Any, msg_dialog).format_secondary_text(message)
        msg_dialog.connect("response", lambda d, r: d.destroy())
        msg_dialog.present()
