"""HypeDevHome — Hosts Editor Widget.

Allows viewing and editing /etc/hosts entries in a user-friendly UI.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from core.utils.hosts import HostsManager  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.empty_state import EmptyState  # noqa: E402

log = logging.getLogger(__name__)


class HostsEditor(Gtk.Box):
    """A list-based editor for the system hosts file."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._manager = HostsManager(HostExecutor())
        self._backup_paths: list[str] = []
        self._host_rows: list[Gtk.Widget] = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Assemble the editor layout."""
        # Main layout: Scrolled window for preferences page
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.append(scrolled)

        self._page = Adw.PreferencesPage()
        scrolled.set_child(self._page)

        # Hosts group
        self._group = Adw.PreferencesGroup(
            title="Host Entries",
            description=(
                "System-wide IP mapping from /etc/hosts. Each save creates a timestamped backup "
                "under ~/.local/share/hypedevhome/hosts-backups/."
            ),
        )
        self._page.add(self._group)

        # Add Button Row
        self._add_row = Adw.ActionRow(
            title="Add New Entry",
            subtitle="Map a new IP to one or more hostnames",
            icon_name="list-add-symbolic",
            activatable=True,
        )
        self._add_row.connect("activated", self._on_add_clicked)
        self._group.add(self._add_row)

        self._export_row = Adw.ActionRow(
            title="Export hosts",
            subtitle="Save the current list to a text file (for review or backup)",
            icon_name="document-save-symbolic",
            activatable=True,
        )
        self._export_row.connect("activated", self._on_export_clicked)
        self._group.add(self._export_row)

        self._import_row = Adw.ActionRow(
            title="Import hosts",
            subtitle="Load a file and replace entries (validates; then saves to /etc/hosts)",
            icon_name="document-open-symbolic",
            activatable=True,
        )
        self._import_row.connect("activated", self._on_import_clicked)
        self._group.add(self._import_row)

        backup_suffix = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._backup_drop = Gtk.DropDown()
        self._backup_drop.set_hexpand(True)
        self._backup_drop.set_model(Gtk.StringList.new(["(no backups yet)"]))
        restore_btn = Gtk.Button(label="Restore…")
        restore_btn.set_tooltip_text("Replace /etc/hosts with selected backup (password required)")
        restore_btn.connect("clicked", self._on_restore_selected_clicked)
        backup_suffix.append(self._backup_drop)
        backup_suffix.append(restore_btn)

        self._restore_row = Adw.ActionRow(
            title="Restore from backup",
            subtitle="Snapshots under ~/.local/share/hypedevhome/hosts-backups/",
            icon_name="document-revert-symbolic",
        )
        self._restore_row.add_suffix(backup_suffix)
        self._group.add(self._restore_row)

        # Empty State (shown if no entries)
        self._empty_state = EmptyState(
            icon_name="applications-internet-symbolic",
            title="No Host Entries",
            description="Your hosts file is currently empty or could not be parsed.",
            button_action=self._on_reload_clicked,
        )
        self._empty_state.set_vexpand(True)
        self._empty_state.hide()
        self.append(self._empty_state)

        # Load data
        GLib.idle_add(self._start_initial_load)

    def _enqueue_async(self, coro: Any) -> None:
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            cast(Any, app).enqueue_task(coro)
        else:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(coro)
            else:
                self._enqueue_async_task = loop.create_task(coro)

    def _start_initial_load(self) -> bool:
        """Begin initial data load via app loop."""
        self._enqueue_async(self._load_data())
        return False

    def _on_reload_clicked(self) -> None:
        """Handle reload button click."""
        self._start_initial_load()

    async def _load_data(self) -> None:
        """Initialize manager and populate list."""
        await self._manager.initialize()
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Update host rows; keep static tool rows (export/import/restore)."""
        for r in self._host_rows:
            self._group.remove(r)
        self._host_rows.clear()
        self._refresh_backup_dropdown()

        entries = self._manager.get_entries()

        if not entries:
            self._empty_state.show()
            self._page.hide()
            return

        self._empty_state.hide()
        self._page.show()

        for i, entry in enumerate(entries):
            row = self._make_host_row(entry, i)
            self._group.add(row)
            self._host_rows.append(row)

    def _make_host_row(self, entry: Any, index: int) -> Adw.ActionRow:
        """Create a row for a host entry."""
        row = Adw.ActionRow()
        row.set_title(entry.ip)
        row.set_subtitle(", ".join(entry.hostnames))

        if entry.comment:
            row.set_subtitle(f"{entry.comment} ({', '.join(entry.hostnames)})")

        # Toggle switch for enabling/disabling
        switch = Gtk.Switch()
        switch.set_active(not entry.is_commented_out)
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect("notify::active", self._on_toggle_activated, index)
        row.add_suffix(switch)

        # Delete button
        del_btn = Gtk.Button(
            icon_name="user-trash-symbolic", tooltip_text="Remove entry", css_classes=["flat"]
        )
        del_btn.connect("clicked", self._on_delete_clicked, index)
        row.add_suffix(del_btn)

        return row

    def _on_toggle_activated(self, switch: Gtk.Switch, _params: Any, index: int) -> None:
        """Handle entry enable/disable."""
        entries = self._manager.get_entries()
        if 0 <= index < len(entries):
            entries[index].is_commented_out = not switch.get_active()

            async def do_save() -> None:
                ok = await self._manager.save()
                if not ok:
                    GLib.idle_add(
                        lambda: emit_utility_toast(
                            "Could not save hosts file (permission denied or write failed)."
                        )
                    )

            self._enqueue_async(do_save())
            log.info("Toggled host entry at index %d", index)

    def _on_delete_clicked(self, _btn: Gtk.Button, index: int) -> None:
        """Handle entry deletion."""

        async def do_delete() -> None:
            entries = self._manager.get_entries()
            if 0 <= index < len(entries):
                entries.pop(index)
                ok = await self._manager.save(entries)
                if not ok:
                    GLib.idle_add(
                        lambda: emit_utility_toast(
                            "Could not save hosts file after removing entry."
                        )
                    )
                GLib.idle_add(self._refresh_list)

        self._enqueue_async(do_delete())

    def _on_add_clicked(self, *_args: Any) -> None:
        """Add row activated (Adw.ActionRow — not a Gtk.Button)."""
        self._open_add_dialog()

    def _refresh_backup_dropdown(self) -> None:
        backups = self._manager.list_backups()
        self._backup_paths = [p for p, _ in backups]
        labels = [lbl for _, lbl in backups] if backups else ["(no backups yet)"]
        self._backup_drop.set_model(Gtk.StringList.new(labels))

    def _on_export_clicked(self, *_args: Any) -> None:
        """Write current entries to a user-chosen file."""
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        dlg = Gtk.FileDialog()
        dlg.set_initial_name("hosts-export.txt")

        def finish(d: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                gfile = d.save_finish(result)
            except Exception as e:
                log.debug("Export dialog finished: %s", e)
                return
            path = gfile.get_path()
            if not path:
                return
            try:
                Path(path).write_text(self._manager.export_content(), encoding="utf-8")
            except OSError as e:
                log.warning("Hosts export write failed: %s", e)
                emit_utility_toast("Could not write hosts export file.")

        dlg.save(parent, None, finish)

    def _on_import_clicked(self, *_args: Any) -> None:
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None
        dlg = Gtk.FileDialog()

        def finish(d: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            try:
                gfile = d.open_finish(result)
            except Exception as e:
                log.debug("Import dialog finished: %s", e)
                return
            path = gfile.get_path()
            if not path:
                return
            try:
                text = Path(path).read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                log.warning("Import read failed: %s", e)
                emit_utility_toast("Could not read the selected hosts file.")
                return

            par = self.get_root()
            pwin = par if isinstance(par, Gtk.Window) else None
            confirm = Adw.MessageDialog(
                transient_for=pwin,
                heading="Replace hosts entries?",
                body="This replaces the in-memory list with the imported file. "
                "You will be asked for a password when saving to /etc/hosts.",
            )
            confirm.add_response("cancel", "Cancel")
            confirm.add_response("apply", "Import")
            confirm.set_response_appearance("apply", Adw.ResponseAppearance.DESTRUCTIVE)
            confirm.set_default_response("cancel")
            confirm.set_close_response("cancel")

            def on_resp(_c: Adw.MessageDialog, response: str) -> None:
                _c.destroy()
                if response != "apply":
                    return

                async def do_import() -> None:
                    ok, msg = self._manager.import_replace_from_lines(text.splitlines())
                    if not ok:
                        log.warning("Import validation failed: %s", msg)
                        GLib.idle_add(
                            lambda m=msg: emit_utility_toast(
                                f"Import rejected: {m}" if m else "Import validation failed."
                            )
                        )
                        return
                    saved = await self._manager.save()
                    if not saved:
                        GLib.idle_add(
                            lambda: emit_utility_toast(
                                "Could not write /etc/hosts after import (permission denied?)."
                            )
                        )
                        return
                    await self._manager.initialize()
                    GLib.idle_add(self._refresh_list)

                self._enqueue_async(do_import())

            confirm.connect("response", on_resp)
            confirm.present()

        dlg.open(parent, None, finish)

    def _on_restore_selected_clicked(self, *_args: Any) -> None:
        """Restore /etc/hosts from the selected backup."""
        idx = self._backup_drop.get_selected()
        if idx < 0 or idx >= len(self._backup_paths):
            return
        path = self._backup_paths[idx]
        backups = self._manager.list_backups()
        label = backups[idx][1] if idx < len(backups) else path
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None

        dlg = Adw.MessageDialog(
            transient_for=parent,
            heading="Restore hosts file?",
            body=f"Replace /etc/hosts with this backup?\n\n{label}",
        )
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("restore", "Restore")
        dlg.set_response_appearance("restore", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.set_close_response("cancel")

        def on_response(_dialog: Adw.MessageDialog, response: str) -> None:
            _dialog.destroy()
            if response != "restore":
                return

            async def do_restore() -> None:
                ok = await self._manager.restore_backup(path)
                if ok:
                    await self._manager.initialize()
                else:
                    GLib.idle_add(
                        lambda: emit_utility_toast(
                            "Could not restore hosts from backup (permission denied or read failed)."
                        )
                    )
                GLib.idle_add(self._refresh_list)

            self._enqueue_async(do_restore())

        dlg.connect("response", on_response)
        dlg.present()

    def _open_add_dialog(self) -> None:
        """Modal dialog to add IP → hostnames."""
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None

        win = Gtk.Window()
        if parent:
            win.set_transient_for(parent)
        win.set_modal(True)
        win.set_title("Add hosts entry")
        win.set_default_size(440, 0)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_start(16)
        outer.set_margin_end(16)
        outer.set_margin_top(16)
        outer.set_margin_bottom(16)

        ip_row = Adw.EntryRow(title="IP address")
        ip_hint = Gtk.Label(label="IPv4 or IPv6", xalign=0.0)
        ip_hint.add_css_class("dim-label")
        ip_hint.add_css_class("caption")
        ip_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ip_block.append(ip_row)
        ip_block.append(ip_hint)

        host_row = Adw.EntryRow(title="Hostnames")
        host_hint = Gtk.Label(label="Space-separated (e.g. app.local api.local)", xalign=0.0)
        host_hint.add_css_class("dim-label")
        host_hint.add_css_class("caption")
        host_block = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        host_block.append(host_row)
        host_block.append(host_hint)

        outer.append(ip_block)
        outer.append(host_block)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: win.close())
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")

        def on_save(_btn: Gtk.Button) -> None:
            ip = ip_row.get_text().strip()
            raw = host_row.get_text().strip()
            names = [x for x in raw.replace(",", " ").split() if x]
            if not ip or not names:
                return

            async def persist() -> None:
                ok = await self._manager.add_entry(ip, names)
                if ok:
                    GLib.idle_add(self._refresh_list)
                    GLib.idle_add(win.close)
                else:
                    log.warning("Could not add hosts entry (validation or save failed)")
                    GLib.idle_add(
                        lambda: emit_utility_toast(
                            "Could not add hosts entry (invalid data, duplicate hostname, or save failed)."
                        )
                    )

            self._enqueue_async(persist())

        save.connect("clicked", on_save)
        btn_row.append(cancel)
        btn_row.append(save)
        outer.append(btn_row)

        win.set_child(outer)
        win.present()
