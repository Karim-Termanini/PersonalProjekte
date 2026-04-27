"""HypeDevHome — Environment Variables Editor Widget.

Allows viewing and editing user and system environment variables.
"""

from __future__ import annotations

import logging
from typing import Any, cast

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from core.utils.env_manager import EnvVarManager, path_value_warnings  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.empty_state import EmptyState  # noqa: E402

log = logging.getLogger(__name__)


class EnvEditor(Gtk.Box):
    """A list-based editor for environment variables."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, **kwargs)
        self._manager = EnvVarManager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Assemble the editor layout."""
        # Scrolled window for preferences
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.append(scrolled)

        self._page = Adw.PreferencesPage()
        scrolled.set_child(self._page)

        # Env group
        self._group = Adw.PreferencesGroup(
            title="Environment Variables",
            description=(
                "Loaded from /etc/environment, ~/.profile, ~/.bashrc, ~/.zshrc, and "
                "~/.config/hypedevhome/env_managed.sh. Edits are saved to the managed file "
                "(add `source` that path in your shell rc to apply)."
            ),
        )
        self._page.add(self._group)

        # Add Button Row
        self._add_row = Adw.ActionRow(
            title="Add Environment Variable",
            subtitle="Define a new variable for your shell environment",
            icon_name="list-add-symbolic",
            activatable=True,
        )
        self._add_row.connect("activated", self._on_add_clicked)
        self._group.add(self._add_row)

        # Empty State
        self._empty_state = EmptyState(
            icon_name="dialog-password-symbolic",
            title="No Environment Variables",
            description="No custom environment variables detected.",
            button_action=self._on_reload_clicked,
        )
        self._empty_state.set_vexpand(True)
        self._empty_state.hide()
        self.append(self._empty_state)

        # Load data
        GLib.idle_add(self._start_initial_load)

    def _start_initial_load(self) -> bool:
        """Begin initial data load via app loop."""
        app = Gtk.Application.get_default()
        if hasattr(app, "enqueue_task"):
            import asyncio

            cast(Any, app).enqueue_task(self._load_data())
        else:
            import asyncio

            self._initial_load_task = asyncio.create_task(self._load_data())
        return False

    def _on_reload_clicked(self) -> None:
        """Handle reload button click."""
        self._start_initial_load()

    async def _load_data(self) -> None:
        """Initialize manager and populate list."""
        await self._manager.initialize()
        self._refresh_list()

    def _refresh_list(self) -> None:
        """Clear and rebuild the list from manager variables."""
        # Rebuild group
        self._page.remove(self._group)
        self._group = Adw.PreferencesGroup(
            title="Environment Variables",
            description=(
                "Loaded from /etc/environment, ~/.profile, ~/.bashrc, ~/.zshrc, and "
                "~/.config/hypedevhome/env_managed.sh. Edits are saved to the managed file."
            ),
        )
        self._page.add(self._group)
        self._group.add(self._add_row)

        variables = self._manager.get_display_variables()

        if not variables:
            self._empty_state.show()
            self._page.hide()
            return

        self._empty_state.hide()
        self._page.show()

        for i, var in enumerate(variables):
            row = self._make_var_row(var, i)
            self._group.add(row)

    def _make_var_row(self, var: Any, index: int) -> Adw.ActionRow:
        """Create a row for an environment variable."""
        row = Adw.ActionRow()
        row.set_title(var.key)
        sub = var.value
        if var.description:
            sub = f"{sub}\n{var.description}"
        row.set_subtitle(sub)

        # Badge for scope
        scope_badge = Gtk.Label(label=var.scope)
        scope_badge.add_css_class("caption")
        scope_badge.add_css_class("dim-label")
        if var.scope == "System":
            scope_badge.add_css_class("accent-label")

        row.add_suffix(scope_badge)

        # Edit button
        edit_btn = Gtk.Button(
            icon_name="document-edit-symbolic", tooltip_text="Edit variable", css_classes=["flat"]
        )
        edit_btn.connect("clicked", self._on_edit_clicked, index)
        row.add_suffix(edit_btn)

        # Delete button
        del_btn = Gtk.Button(
            icon_name="user-trash-symbolic", tooltip_text="Remove variable", css_classes=["flat"]
        )
        del_btn.connect("clicked", self._on_delete_clicked, index)
        row.add_suffix(del_btn)

        return row

    def _enqueue_async(self, coro: Any) -> None:
        """Run coroutine on the app background loop when available."""
        app = Gtk.Application.get_default()
        if app and hasattr(app, "enqueue_task"):
            cast(Any, app).enqueue_task(coro)
        else:
            import asyncio

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                asyncio.run(coro)
            else:
                self._enqueue_async_task = loop.create_task(coro)

    def _on_edit_clicked(self, _btn: Gtk.Button, index: int) -> None:
        """Handle variable edit."""
        variables = self._manager.get_variables()
        if not (0 <= index < len(variables)):
            return
        real = self._manager.get_variables()
        if not (0 <= index < len(real)):
            return
        var = real[index]
        self._open_var_dialog(index, var.key, var.value)

    def _on_delete_clicked(self, _btn: Gtk.Button, index: int) -> None:
        """Handle variable deletion."""

        async def do_delete() -> None:
            ok = await self._manager.remove_variable(index)
            if not ok:
                GLib.idle_add(
                    lambda: emit_utility_toast(
                        "Could not remove environment variable (save failed)."
                    )
                )
            GLib.idle_add(self._refresh_list)

        self._enqueue_async(do_delete())

    def _on_add_clicked(self, *_args: Any) -> None:
        """Add row activated (Adw.ActionRow — no Gtk.Button)."""
        self._open_var_dialog(None, "", "")

    def _open_var_dialog(self, index: int | None, key: str, value: str) -> None:
        """Modal editor for one variable."""
        root = self.get_root()
        parent = root if isinstance(root, Gtk.Window) else None

        win = Gtk.Window()
        if parent:
            win.set_transient_for(parent)
        win.set_modal(True)
        win.set_title("Add variable" if index is None else "Edit variable")
        win.set_default_size(420, 0)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        outer.set_margin_start(16)
        outer.set_margin_end(16)
        outer.set_margin_top(16)
        outer.set_margin_bottom(16)

        key_row = Adw.EntryRow(title="Name")
        key_row.set_text(key)
        val_row = Adw.EntryRow(title="Value")
        val_row.set_text(value)

        outer.append(key_row)
        outer.append(val_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_row.set_halign(Gtk.Align.END)

        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda *_: win.close())
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")

        def on_save(_btn: Gtk.Button) -> None:
            k = key_row.get_text().strip()
            v = val_row.get_text()
            if not k:
                return
            if k == "PATH":
                warns = path_value_warnings(v)
                if warns:

                    def on_warn(_d: Adw.MessageDialog, response: str) -> None:
                        _d.destroy()
                        if response != "continue":
                            return
                        self._enqueue_async(_persist_env(k, v, index, win))

                    wd = Adw.MessageDialog(
                        transient_for=parent,
                        heading="PATH warning",
                        body=warns[0],
                    )
                    wd.add_response("cancel", "Cancel")
                    wd.add_response("continue", "Save anyway")
                    wd.set_default_response("cancel")
                    wd.connect("response", on_warn)
                    wd.present()
                    return

            self._enqueue_async(_persist_env(k, v, index, win))

        async def _persist_env(k: str, v: str, idx: int | None, w: Gtk.Window) -> None:
            if idx is None:
                ok = await self._manager.add_variable(k, v)
            else:
                ok = await self._manager.update_variable(idx, k, v)
            if not ok:
                log.warning("Could not save environment variable")
                GLib.idle_add(
                    lambda: emit_utility_toast(
                        "Could not save variable (duplicate name, invalid name, or write failed)."
                    )
                )
                GLib.idle_add(self._refresh_list)
                return
            GLib.idle_add(self._refresh_list)
            GLib.idle_add(w.close)

        save.connect("clicked", on_save)
        btn_row.append(cancel)
        btn_row.append(save)
        outer.append(btn_row)

        win.set_child(outer)
        win.present()
