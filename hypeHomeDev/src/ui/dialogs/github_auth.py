"""HypeDevHome — GitHub authentication dialog.

Dialog for entering and validating GitHub Personal Access Tokens.
"""

from __future__ import annotations

import logging

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, Gtk, Pango  # noqa: E402

from core.github.auth import get_auth_manager  # noqa: E402

log = logging.getLogger(__name__)


class GitHubAuthDialog(Adw.Window):
    """Dialog for GitHub authentication."""

    def __init__(self, parent: Gtk.Window | None = None) -> None:
        """Initialize the GitHub authentication dialog.

        Args:
            parent: Parent window for dialog
        """
        super().__init__(
            title="GitHub Authentication",
            transient_for=parent,
            modal=True,
            default_width=400,
            default_height=300,
        )

        self._auth_manager = get_auth_manager()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Setup dialog UI."""
        # Create header
        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="GitHub Authentication"))

        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(12)
        main_box.set_margin_end(12)

        # Information label
        info_label = Gtk.Label(
            label="Enter your GitHub Personal Access Token (PAT) to connect to GitHub.",
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD,
        )
        info_label.add_css_class("body")

        # Token entry
        token_label = Gtk.Label(label="Personal Access Token:")
        token_label.set_halign(Gtk.Align.START)
        token_label.add_css_class("heading")

        self._token_entry = Gtk.PasswordEntry()
        self._token_entry.set_hexpand(True)
        self._token_entry.connect("activate", self._on_validate_token)

        # Validation button
        self._validate_button = Gtk.Button(label="Validate & Save")
        self._validate_button.add_css_class("suggested-action")
        self._validate_button.connect("clicked", self._on_validate_token)

        # Status area
        self._status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._status_box.set_visible(False)

        # Help text
        help_label = Gtk.Label(
            label="Create a token at: https://github.com/settings/tokens\n"
            "Required scopes: repo, read:user, read:org",
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD,
        )
        help_label.add_css_class("caption")
        help_label.add_css_class("dim-label")

        # Add widgets to main box
        main_box.append(info_label)
        main_box.append(token_label)
        main_box.append(self._token_entry)
        main_box.append(self._validate_button)
        main_box.append(self._status_box)
        main_box.append(help_label)

        # Set content
        self.set_content(main_box)

    def _on_validate_token(self, *args) -> None:
        """Validate the entered token."""
        token = self._token_entry.get_text().strip()

        if not token:
            self._show_error("Please enter a token")
            return

        # Show loading
        self._show_loading("Validating token...")

        # Validate token (this would be async in real implementation)
        # For now, use mock validation
        is_valid, username, scopes = self._auth_manager.validate_token(token)

        if is_valid and username and scopes:
            # Save credentials
            success = self._auth_manager.set_credentials(token, username, scopes)

            if success:
                self._show_success(f"Connected as {username}")
                # Close dialog after delay
                from gi.repository import GLib

                GLib.timeout_add(1500, self.close)
            else:
                self._show_error("Failed to save credentials")
        else:
            self._show_error("Invalid token. Please check your token and try again.")

    def _show_loading(self, message: str) -> None:
        """Show loading status."""
        self._clear_status()

        loading_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        spinner = Gtk.Spinner()
        spinner.start()

        label = Gtk.Label(label=message)

        loading_box.append(spinner)
        loading_box.append(label)

        self._status_box.append(loading_box)
        self._status_box.set_visible(True)

    def _show_success(self, message: str) -> None:
        """Show success status."""
        self._clear_status()

        success_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
        icon.add_css_class("success")

        label = Gtk.Label(label=message)
        label.add_css_class("success")

        success_box.append(icon)
        success_box.append(label)

        self._status_box.append(success_box)
        self._status_box.set_visible(True)

    def _show_error(self, message: str) -> None:
        """Show error status."""
        self._clear_status()

        error_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        icon = Gtk.Image.new_from_icon_name("dialog-error-symbolic")
        icon.add_css_class("error")

        label = Gtk.Label(label=message)
        label.add_css_class("error")

        error_box.append(icon)
        error_box.append(label)

        self._status_box.append(error_box)
        self._status_box.set_visible(True)

    def _clear_status(self) -> None:
        """Clear status area."""
        for child in self._status_box:
            self._status_box.remove(child)
        self._status_box.set_visible(False)
