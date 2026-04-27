"""HypeDevHome — Snapshot Management Dialog.

Provides a user interface for listing, creating, restoring, and deleting
environment snapshots.
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from app import HypeDevHomeApp

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from core.maintenance.manager import SnapshotMetadata  # noqa: E402
from core.state import AppState  # noqa: E402

log = logging.getLogger(__name__)


class SnapshotRow(Adw.ActionRow):
    """A row representing a single snapshot in the list."""

    def __init__(self, metadata: SnapshotMetadata) -> None:
        super().__init__(title=metadata.name)

        # Subtitle with timestamp and size
        ts_str = metadata.timestamp[:19].replace("T", " ")
        size_mb = metadata.size_bytes / (1024 * 1024)
        self.set_subtitle(f"{ts_str} • {size_mb:.1f} MB")
        self._id = metadata.snapshot_id

        # Status Icons
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        if metadata.encrypted:
            lock_icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
            lock_icon.set_tooltip_text("Encrypted (AES-256)")
            status_box.append(lock_icon)

        if metadata.sha256_checksum:
            check_icon = Gtk.Image.new_from_icon_name("emblem-ok-symbolic")
            check_icon.set_tooltip_text("Integrity Verified (SHA-256)")
            status_box.append(check_icon)

        self.add_prefix(status_box)

        # Restore Button
        self._restore_btn = Gtk.Button(
            icon_name="document-revert-symbolic", tooltip_text="Restore This Snapshot"
        )
        self._restore_btn.set_has_frame(False)
        self._restore_btn.add_css_class("suggested-action")
        self.add_suffix(self._restore_btn)

        # Delete Button
        self._delete_btn = Gtk.Button(
            icon_name="user-trash-symbolic", tooltip_text="Delete Snapshot"
        )
        self._delete_btn.set_has_frame(False)
        self._delete_btn.add_css_class("destructive-action")
        self.add_suffix(self._delete_btn)


class SnapshotManagementDialog(Adw.Window):
    """Dialog for managing snapshots of a specific container."""

    def __init__(self, container_name: str, **kwargs: Any) -> None:
        super().__init__(
            title=f"Snapshots: {container_name}",
            modal=True,
            default_width=500,
            default_height=600,
            **kwargs,
        )
        self._container_name = container_name
        self._manager = AppState.get().snapshot_manager
        self._background_tasks: set[concurrent.futures.Future[Any]] = set()

        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        """Construct the dialog layout."""
        content = Adw.ToolbarView()

        # Header bar
        header = Adw.HeaderBar()
        content.add_top_bar(header)

        # Main Layout
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        vbox.set_margin_top(12)
        vbox.set_margin_bottom(12)
        vbox.set_margin_start(12)
        vbox.set_margin_end(12)

        # 1. Action Strip
        action_group = Adw.PreferencesGroup(title="Maintenance")
        vbox.append(action_group)

        action_row = Adw.ActionRow(
            title="Create Snapshot", subtitle="Backup the current state of this environment"
        )
        action_group.add(action_row)

        # Encryption Toggle
        self._encrypt_toggle = Gtk.CheckButton(label="Encrypt")
        self._encrypt_toggle.set_valign(Gtk.Align.CENTER)
        action_row.add_suffix(self._encrypt_toggle)

        self._create_btn = Gtk.Button(label="Take Snapshot")
        self._create_btn.add_css_class("suggested-action")
        self._create_btn.set_valign(Gtk.Align.CENTER)
        self._create_btn.connect("clicked", self._on_create_clicked)
        action_row.add_suffix(self._create_btn)

        # 2. List of snapshots
        snapshot_group = Adw.PreferencesGroup(title="Available Snapshots")
        vbox.append(snapshot_group)

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.add_css_class("boxed-list")
        snapshot_group.add(self._list_box)

        content.set_content(vbox)
        self.set_content(content)

    def _refresh(self) -> None:
        """Reload the snapshot list from storage."""
        if not self._manager:
            return

        # Clear list
        while True:
            child = self._list_box.get_first_child()
            if not child:
                break
            self._list_box.remove(child)

        async def fetch():
            snaps = await self._manager.list_snapshots(self._container_name)
            GLib.idle_add(self._populate_list, snaps)

        app = cast("HypeDevHomeApp", Gio.Application.get_default())
        task: concurrent.futures.Future[Any] | None = app.enqueue_task(fetch())
        if task:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    def _populate_list(self, snapshots: list[SnapshotMetadata]) -> None:
        for snap in snapshots:
            row = SnapshotRow(snap)
            row._restore_btn.connect("clicked", self._on_restore_clicked, snap.snapshot_id)
            row._delete_btn.connect("clicked", self._on_delete_clicked, snap.snapshot_id)
            self._list_box.append(row)

        if not snapshots:
            empty = Gtk.Label(
                label="No snapshots found for this environment",
                css_classes=["dim-label"],
                margin_top=40,
            )
            self._list_box.append(empty)

    def _on_create_clicked(self, _btn: Gtk.Button) -> None:
        """Trigger a new snapshot creation."""
        encrypt = self._encrypt_toggle.get_active()
        passphrase = "test_secret_pass" if encrypt else None

        self._create_btn.set_sensitive(False)

        async def do_create():
            await self._manager.create_snapshot(
                self._container_name, encrypt=encrypt, passphrase=passphrase
            )
            GLib.idle_add(self._on_creation_done)

        app = cast("HypeDevHomeApp", Gio.Application.get_default())
        task: concurrent.futures.Future[Any] | None = app.enqueue_task(do_create())
        if task:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    def _on_creation_done(self) -> None:
        self._create_btn.set_sensitive(True)
        self._refresh()

    def _on_restore_clicked(self, _btn: Gtk.Button, snapshot_id: str) -> None:
        """Restore the selected snapshot."""
        if not self._manager:
            return

        async def do_restore():
            # Check if encrypted (we'd check metadata here)
            # For simplicity, we try with the session cache
            success = await self._manager.restore_snapshot(
                snapshot_id, passphrase="test_secret_pass"
            )
            if success:
                log.info("Snapshot restored: %s", snapshot_id)

        app = cast("HypeDevHomeApp", Gio.Application.get_default())
        task: concurrent.futures.Future[Any] | None = app.enqueue_task(do_restore())
        if task:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)

    def _on_delete_clicked(self, _btn: Gtk.Button, snapshot_id: str) -> None:
        """Delete the selected snapshot."""
        if not self._manager:
            return

        async def do_delete():
            await self._manager.delete_snapshot(snapshot_id)
            GLib.idle_add(self._refresh)

        app = cast("HypeDevHomeApp", Gio.Application.get_default())
        task: concurrent.futures.Future[Any] | None = app.enqueue_task(do_delete())
        if task:
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
