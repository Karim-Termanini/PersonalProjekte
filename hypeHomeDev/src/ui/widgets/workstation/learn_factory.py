"""Generic, data-driven Workstation Learn cheatsheet renderer.

Phase 1 goal:
- Render cheatsheets from JSON data (titles, descriptions, link cards, code blocks, text blocks)
- Centralize UI rendering logic so individual cheatsheets become thin wrappers + data files

Security (Phase 7.5): ``host_checks`` with ``type == "command_exists"`` must pass the program name
through :func:`argv_host_command_exists_probe` (``shlex.quote`` + ``command -v``). Do not add new
check types that interpolate JSON into shell strings without quoting or argv-only execution.
"""

from __future__ import annotations

import logging
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

from core.setup.host_executor import HostExecutor  # noqa: E402
from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.nav_helper import (  # noqa: E402
    copy_plain_text_to_clipboard,
    navigate_main_window,
)
from ui.widgets.workstation.workstation_learning_scroll import (  # noqa: E402
    learn_colored_title,
    scroll_learn_search_to_first_hit,
)
from ui.widgets.workstation.workstation_utils import (  # noqa: E402
    _bg,
    safe_load_catalog,
    sanitize_pango_markup,
)

log = logging.getLogger(__name__)


def argv_host_command_exists_probe(program: str) -> list[str]:
    """Build argv for a host-side ``command -v`` check; *program* is passed through :func:`shlex.quote`."""
    quoted = shlex.quote(program.strip())
    return ["sh", "-lc", f"command -v {quoted} >/dev/null 2>&1 && echo yes || echo no"]


@dataclass(frozen=True)
class CheatsheetItem:
    type: str
    # Flexible payload depending on `type`
    data: dict[str, Any]


def _copy_cmd(cmd: str) -> None:
    if copy_plain_text_to_clipboard(cmd):
        emit_utility_toast("Command copied.", "info", timeout=4)
    else:
        emit_utility_toast("Could not copy to clipboard.", "error")


def _load_json(path: Path) -> dict[str, Any]:
    """Load cheatsheet JSON; on I/O or parse errors returns a safe dict (see ``safe_load_catalog``)."""
    return safe_load_catalog(path)


class WorkstationLearnFactoryPage(Gtk.Box):
    """Render a cheatsheet defined by JSON.

    Expected JSON shape (minimal):
    {
      "id": "bash",
      "columns": 2,
      "languages": [{"id":"en","label":"English"}, ...],
      "i18n": {
        "en": {
          "lang_row_title":"Language",
          "search_label":"Search",
          "search_placeholder":"...",
          "groups":[
            {"id":"intro","title":"...","description":"...","items":[{"type":"link",...}, ...]},
            ...
          ]
        },
        "de": {...}
      }
    }
    """

    def __init__(self, *, data_path: str | Path, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, **kwargs)
        self.add_css_class("workstation-learn-colored-titles")
        self.set_margin_start(14)
        self.set_margin_end(14)
        self.set_margin_top(10)
        self.set_margin_bottom(18)

        self._data_path = Path(data_path)
        self._data = _load_json(self._data_path)

        # UI state
        self._lang_ids: list[str] = []
        self._lang_labels: list[str] = []
        self._lang_id: str = "en"
        raw_columns = self._data.get("columns", 2)
        try:
            self._columns_n = int(raw_columns)
        except (TypeError, ValueError):
            log.warning("Invalid 'columns' value %r, defaulting to 2", raw_columns)
            self._columns_n = 2
        if self._columns_n < 1:
            self._columns_n = 1
        elif self._columns_n > 4:
            self._columns_n = 4

        self._search_targets: list[tuple[Gtk.Revealer, str, frozenset[str]]] = []
        self._title_color_idx: int = 0
        self._chip_ids: list[str] = [str(x) for x in (self._data.get("filter_chips") or []) if str(x)]
        self._chip_toggles: dict[str, Gtk.ToggleButton] = {}

        self._executor = HostExecutor()

        # Parse languages
        langs = self._data.get("languages") or []
        for entry in langs:
            if not isinstance(entry, dict):
                continue
            lid = entry.get("id")
            lbl = entry.get("label")
            if isinstance(lid, str) and isinstance(lbl, str):
                self._lang_ids.append(lid)
                self._lang_labels.append(lbl)

        if not self._lang_ids:
            raise ValueError(f"Cheatsheet JSON must define non-empty `languages`: {self._data_path}")

        self._lang_id = self._lang_ids[0]

        # Language selector
        lang_group = Adw.PreferencesGroup()
        lang_group.add_css_class(self._group_css_class_for_lang_selector())
        self._lang_row = Adw.ComboRow()
        self._lang_row.set_model(Gtk.StringList.new(self._lang_labels))
        self._lang_row.set_selected(0)
        lang_group.add(self._lang_row)
        self.append(lang_group)

        err = self._data.get("error")
        if isinstance(err, str) and err.strip():
            banner = Gtk.Label(label=err, wrap=True, xalign=0.0)
            banner.add_css_class("error")
            banner.set_margin_start(6)
            banner.set_margin_end(6)
            banner.set_margin_bottom(8)
            self.append(banner)

        # Optional action buttons
        self._build_action_buttons_if_any()

        # Optional host status badges
        self._host_badges_box: Gtk.Box | None = None
        self._build_host_checks_if_any()

        # Search row
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        search_row.set_margin_start(6)
        search_row.set_margin_end(6)
        search_row.set_margin_bottom(4)
        self._search_lbl = Gtk.Label()
        self._search_lbl.set_valign(Gtk.Align.CENTER)
        self._search_lbl.add_css_class("dim-label")

        self._search = Gtk.SearchEntry()
        self._search.set_hexpand(True)
        self._search.connect("notify::text", self._on_search_changed)

        search_row.append(self._search_lbl)
        search_row.append(self._search)
        self.append(search_row)

        # Optional filter chips (intersection-based visibility)
        self._chip_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._chip_row.set_margin_start(4)
        self._chip_row.set_margin_end(4)
        self._chip_row.set_margin_bottom(4)
        self._chip_label = Gtk.Label()
        self._chip_label.set_valign(Gtk.Align.CENTER)
        self._chip_label.add_css_class("dim-label")
        self._chip_row.append(self._chip_label)
        if self._chip_ids:
            for cid in self._chip_ids:
                tb = Gtk.ToggleButton()
                tb.connect("toggled", self._on_search_changed)
                self._chip_toggles[cid] = tb
                self._chip_row.append(tb)
            self.append(self._chip_row)

        # Columns
        # Do not vexpand: it steals all height from parent Gtk.ScrolledWindow and
        # prevents vertical scrolling (Docker Docs, Neovim cheatsheet, etc.).
        self._columns = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=28,
            vexpand=False,
            hexpand=True,
        )
        self._columns.set_valign(Gtk.Align.START)
        self._columns.set_homogeneous(True)

        self._col_boxes: list[Gtk.Box] = [self._column() for _ in range(self._columns_n)]
        for col in self._col_boxes:
            self._columns.append(col)
        self.append(self._columns)

        # Initial build
        self._apply_lang_ui()
        self._rebuild_cheatsheet()
        self._lang_row.connect("notify::selected", self._on_lang_selected)

    def _build_action_buttons_if_any(self) -> None:
        action_buttons = self._data.get("action_buttons") or []
        if not isinstance(action_buttons, list) or not action_buttons:
            return
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.set_margin_start(4)
        row.set_margin_end(4)
        row.set_margin_bottom(2)
        for item in action_buttons:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "") or "")
            action = str(item.get("action", "") or "")
            target = str(item.get("target", "") or "")
            if not label:
                continue
            btn = Gtk.Button(label=label)
            if bool(item.get("suggested", False)):
                btn.add_css_class("suggested-action")
            if action == "navigate" and target:
                btn.connect("clicked", self._on_action_navigate_clicked, target)
            row.append(btn)
        self.append(row)

    def _on_action_navigate_clicked(self, _btn: Gtk.Button, target: str) -> None:
        if not navigate_main_window(target):
            emit_utility_toast(f"Could not open {target}.", "error")
            return
        emit_utility_toast(f"Opened {target}.", "info", timeout=4)

    def _build_host_checks_if_any(self) -> None:
        host_checks = self._data.get("host_checks") or []
        if not isinstance(host_checks, list) or not host_checks:
            return

        self._host_badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._host_badges_box.set_margin_start(4)
        self._host_badges_box.set_margin_end(4)
        self._host_badges_box.set_margin_bottom(4)

        for item in host_checks:
            if not isinstance(item, dict):
                continue

            label_ok = str(item.get("label_ok", "") or "")
            label_missing = str(item.get("label_missing", "") or "")
            if not label_ok and not label_missing:
                continue

            # Create badge early (UI thread)
            chip = Gtk.Label(label="Checking...")
            chip.add_css_class("caption")
            chip.add_css_class("dim-label")
            detail = str(item.get("detail", "") or "")
            if detail:
                chip.set_tooltip_text(detail)
            self._host_badges_box.append(chip)

            # Spawn check (Background thread)
            def _run_check_async(c=chip, i=item, lok=label_ok, lmiss=label_missing) -> None:
                check_type = str(i.get("type", "") or "")
                ok = False

                if check_type == "command_exists":
                    cmd = str(i.get("command", "") or "").strip()
                    if cmd:
                        res = self._executor.run_sync(argv_host_command_exists_probe(cmd))
                        ok = bool(res.success and res.stdout.strip().lower() == "yes")

                final_text = lok if ok else lmiss
                GLib.idle_add(c.set_label, final_text)

            _bg(_run_check_async)

        if self._host_badges_box.get_first_child() is not None:
            self.append(self._host_badges_box)

    def _group_css_class_for_lang_selector(self) -> str:
        # Reuse bash cheatsheet styling hooks so the generic builder matches existing look
        return "bash-cheatsheet-group"

    def _get_lang_payload(self) -> dict[str, Any]:
        i18n = self._data.get("i18n") or {}
        payload = i18n.get(self._lang_id)
        if not isinstance(payload, dict) or not payload.get("groups"):
            # UI ARTIFACT FIX: Fallback to 'en' content if the localized version is empty or missing
            # ensures we don't show a 'Blank Hub' (Negative Feedback Fix)
            payload = i18n.get("en") or (i18n.get(self._lang_ids[0]) if self._lang_ids else {}) or {}
        return payload

    def _apply_lang_ui(self) -> None:
        u = self._get_lang_payload()
        self._lang_row.set_title(str(u.get("lang_row_title", "")))
        self._search_lbl.set_label(str(u.get("search_label", "")))
        self._search.set_placeholder_text(str(u.get("search_placeholder", "")))
        if self._chip_ids:
            self._chip_label.set_label(str(u.get("chip_row_label", "Modes")))
            labels = u.get("chip_labels") or {}
            tips = u.get("chip_tooltips") or {}
            for cid, tb in self._chip_toggles.items():
                tb.set_label(str(labels.get(cid, cid.upper())))
                tip = str(tips.get(cid, "") or "")
                if tip:
                    tb.set_tooltip_text(tip)

    def _clear_columns(self) -> None:
        for col in self._col_boxes:
            while col.get_first_child() is not None:
                col.remove(col.get_first_child())
        self._search_targets.clear()
        self._title_color_idx = 0

    def _on_lang_selected(self, row: Adw.ComboRow, _pspec: Any) -> None:
        i = row.get_selected()
        if not isinstance(i, int) or i < 0 or i >= len(self._lang_ids):
            return
        lid = self._lang_ids[i]
        if lid == self._lang_id:
            return
        self._lang_id = lid
        self._apply_lang_ui()
        self._rebuild_cheatsheet()

    def _on_search_changed(self, *_args: Any) -> None:
        raw = self._search.get_text().strip().lower()
        parts = [p for p in raw.split() if p]
        active = frozenset(cid for cid, tb in self._chip_toggles.items() if tb.get_active())
        for revealer, blob, tags in self._search_targets:
            ok_text = not parts or all(p in blob for p in parts)
            ok_tags = True if not active or not tags else bool(tags & active)
            revealer.set_reveal_child(ok_text and ok_tags)
        scroll_learn_search_to_first_hit(self._search_targets, has_query=bool(parts) or bool(active))

    @staticmethod
    def _column() -> Gtk.Box:
        return Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)

    def _rebuild_cheatsheet(self) -> None:
        self._clear_columns()
        u = self._get_lang_payload()
        groups = u.get("groups") or []
        if not groups:
            en_payload = (self._data.get("i18n") or {}).get("en") or {}
            groups = en_payload.get("groups") or []
        if not isinstance(groups, list):
            return

        for idx, group_entry in enumerate(groups):
            if not isinstance(group_entry, dict):
                continue
            col = self._col_boxes[idx % len(self._col_boxes)]
            self._append_group(col, group_entry)

    def _append_group(self, col: Gtk.Box, group_entry: dict[str, Any]) -> None:
        title = str(group_entry.get("title", "") or "")
        description = str(group_entry.get("description", "") or "")
        group_id = str(group_entry.get("id", "") or "")
        items = group_entry.get("items") or []
        group_tags_raw = group_entry.get("tags") or []
        group_tags = {
            str(t).strip().lower()
            for t in group_tags_raw
            if isinstance(t, str) and str(t).strip()
        }
        extra_search = str(group_entry.get("extra_search", "") or "")

        if title:
            title_markup = learn_colored_title(title, self._title_color_idx)
            self._title_color_idx += 1
        else:
            title_markup = ""

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        outer.set_margin_bottom(12)

        # UI ARTIFACT FIX: Finding 5/6 context - sanitize Pango markup descriptions
        safe_description = sanitize_pango_markup(description)
        g = Adw.PreferencesGroup(title=title_markup, description=safe_description)
        g.add_css_class("bash-cheatsheet-group")

        revealer = Gtk.Revealer()
        revealer.set_child(g)
        revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        revealer.set_reveal_child(True)
        outer.append(revealer)
        col.append(outer)

        blob_parts: list[str] = []
        if title:
            blob_parts.append(title)
        if description:
            blob_parts.append(description)
        if extra_search:
            blob_parts.append(extra_search)

        item_tags: set[str] = set()

        for item_entry in items:
            if not isinstance(item_entry, dict):
                continue
            item_type = str(item_entry.get("type", "") or "")
            item = CheatsheetItem(type=item_type, data=item_entry)
            self._append_item(g, item)

            # Search blob
            if item.type == "code":
                code = str(item.data.get("code", "") or "")
                blob_parts.append(code)
            elif item.type == "text":
                txt = str(item.data.get("text", "") or "")
                blob_parts.append(txt)
            elif item.type == "link":
                label = str(item.data.get("label", "") or "")
                url = str(item.data.get("url", "") or "")
                blob_parts.append(label)
                blob_parts.append(url)
            elif item.type == "table":
                rows = item.data.get("rows") or []
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        blob_parts.append(str(row.get("key", "") or ""))
                        blob_parts.append(str(row.get("value", "") or ""))
            raw_item_tags = item.data.get("tags") or []
            if isinstance(raw_item_tags, list):
                for t in raw_item_tags:
                    if isinstance(t, str) and t.strip():
                        item_tags.add(t.strip().lower())

        blob = " ".join(" ".join(blob_parts).lower().split())
        self._search_targets.append((revealer, blob, frozenset(group_tags | item_tags)))

        # Keep ids for future enhancements (analytics/debugging)
        _ = group_id

    def _append_item(self, group_widget: Adw.PreferencesGroup, item: CheatsheetItem) -> None:
        if item.type == "link":
            self._add_link_row(group_widget, item.data)
        elif item.type == "code":
            self._add_code_block(group_widget, str(item.data.get("code", "") or ""))
        elif item.type == "text":
            self._add_text_row(group_widget, str(item.data.get("text", "") or ""))
        elif item.type == "table":
            self._add_table(group_widget, item.data)
        else:
            log.warning("Unknown cheatsheet item type: %s", item.type)

    def _add_text_row(self, group_widget: Adw.PreferencesGroup, text: str) -> None:
        if not text:
            return
        lbl = Gtk.Label(label=text, xalign=0.0, wrap=True)
        lbl.add_css_class("bash-cheatsheet-text")
        lbl.set_margin_start(16)
        lbl.set_margin_end(16)
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(8)
        lbl.set_max_width_chars(60)
        group_widget.add(lbl)

    def _add_code_block(self, group_widget: Adw.PreferencesGroup, code: str) -> None:
        if not code:
            return
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer_box.set_margin_start(16)
        outer_box.set_margin_end(16)
        outer_box.set_margin_top(10)
        outer_box.set_margin_bottom(10)
        outer_box.add_css_class("card")
        outer_box.add_css_class("bash-code-block")

        lines = code.split("\n")
        for line in lines:
            if not line.strip():
                continue
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_box.set_margin_start(16)
            row_box.set_margin_end(12)
            row_box.set_margin_top(10)
            row_box.set_margin_bottom(10)

            lbl = Gtk.Label(
                label=line,
                xalign=0.0,
                wrap=True,
                wrap_mode=Pango.WrapMode.WORD_CHAR,
            )
            lbl.add_css_class("bash-code-label")
            lbl.set_hexpand(True)
            lbl.set_selectable(True)
            row_box.append(lbl)

            copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.set_has_frame(False)
            copy_btn.add_css_class("flat")
            copy_btn.connect("clicked", lambda _b, text=line: _copy_cmd(text))
            row_box.append(copy_btn)

            outer_box.append(row_box)

        group_widget.add(outer_box)

    def _add_link_row(self, group_widget: Adw.PreferencesGroup, data: dict[str, Any]) -> None:
        title = str(data.get("label", "") or "")
        url = str(data.get("url", "") or "")
        if not title and not url:
            return

        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_margin_start(16)
        container.set_margin_end(16)
        container.set_margin_top(10)
        container.set_margin_bottom(10)
        container.add_css_class("bash-link-card")

        row = Adw.ActionRow()
        row.set_use_markup(False)
        row.set_title(title)
        row.set_subtitle(url)
        row.set_margin_start(16)
        row.set_margin_end(16)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        row.add_css_class("bash-link-row")

        # UI ARTIFACT FIX: Finding 15 refactor - use semantic CSS classes instead of get_first_child()
        # targeting handled in gtk.css

        btn = Gtk.Button(label="Open")
        btn.set_valign(Gtk.Align.CENTER)
        btn.connect(
            "clicked",
            lambda *_: self._open_url(url),
        )
        row.add_suffix(btn)

        container.append(row)
        group_widget.add(container)

    def _add_table(self, group_widget: Adw.PreferencesGroup, data: dict[str, Any]) -> None:
        rows = data.get("rows") or []
        if not isinstance(rows, list):
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key", "") or "")
            val = str(row.get("value", "") or "")
            warn = bool(row.get("warn", False))
            if key:
                self._add_table_row(group_widget, key=key, value=val, warn=warn)

    def _add_table_row(self, group_widget: Adw.PreferencesGroup, *, key: str, value: str, warn: bool = False) -> None:
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_margin_start(16)
        container.set_margin_end(16)
        container.set_margin_top(10)
        container.set_margin_bottom(10)
        container.add_css_class("bash-table-card")

        row = Adw.ActionRow()
        row.set_use_markup(False)
        row.set_title(key)
        row.set_subtitle(("⚠ " if warn else "") + value)
        row.set_margin_start(16)
        row.set_margin_end(16)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        row.add_css_class("bash-table-row")

        # UI ARTIFACT FIX: Finding 15 refactor - use semantic CSS classes instead of get_first_child()

        btn = Gtk.Button(icon_name="edit-copy-symbolic")
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_has_frame(False)
        btn.add_css_class("flat")
        btn.connect("clicked", lambda _b, k=key: _copy_cmd(k))
        row.add_suffix(btn)

        container.append(row)
        group_widget.add(container)

    @staticmethod
    def _open_url(url: str) -> None:
        import webbrowser

        webbrowser.open(url)

