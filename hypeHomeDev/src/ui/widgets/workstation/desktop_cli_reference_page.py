"""CLI reference cheatsheet (Tools → Config → CLI; search + two columns + copy rows)."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, GLib, GObject, Gtk  # noqa: E402

from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.nav_helper import copy_plain_text_to_clipboard  # noqa: E402
from ui.widgets.workstation.workstation_learning_scroll import (  # noqa: E402
    learn_colored_title,
    scroll_learn_search_to_first_hit,
)

_SECTION_SPLIT = re.compile(r"(?m)^##\s+")
_FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
_TABLE_SEP = re.compile(r"^\|?\s*:?[-]+\s*(\|\s*:?[-]+\s*)+\|?\s*$")
_PREAMBLE_MAX_LINKS = 220

_LANG_CODES = ("en", "de", "ar")

_CLI_UI: dict[str, dict[str, str]] = {
    "en": {
        "lang_row_title": "Language",
        "intro_title": "CLI cheatsheet",
        "intro_desc": (
            "Same layout as Neovim: search filters groups, two equal columns, each line is a row. "
            "Use the copy icon (or click the row) for commands; overview rows copy or open URLs."
        ),
        "search_placeholder": "Filter sections and commands…",
        "hint": (
            "Type words to narrow groups (matches title, description, and row text). "
            "Click a row or the copy icon to copy the line; for URL-only rows, click opens the article."
        ),
        "overview_title": "Overview — doc links",
        "overview_desc": (
            "Each row is one command article. Copy puts the URL on the clipboard; search by tool name."
        ),
        "table_row": "Table row",
    },
    "de": {
        "lang_row_title": "Sprache",
        "intro_title": "CLI-Spickzettel",
        "intro_desc": (
            "Gleicher Aufbau wie Neovim: Suche filtert Gruppen, zwei gleich breite Spalten, jede Zeile eine Aktion. "
            "Zum Kopieren das Symbol nutzen oder die Zeile anklicken; in der Übersicht URLs kopieren oder öffnen."
        ),
        "search_placeholder": "Abschnitte und Befehle filtern…",
        "hint": (
            "Wörter eingeben, um Gruppen einzugrenzen (Titel, Beschreibung, Zeilentext). "
            "Zeile oder Kopiersymbol: Zeile kopieren; nur URL: Klick öffnet den Artikel."
        ),
        "overview_title": "Übersicht — Dokumentationslinks",
        "overview_desc": (
            "Jede Zeile ist ein Befehlsartikel. Kopieren legt die URL in die Zwischenablage; Suche nach Werkzeugname."
        ),
        "table_row": "Tabellenzeile",
    },
    "ar": {
        "lang_row_title": "اللغة",
        "intro_title": "مرجع أوامر الطرفية (CLI)",
        "intro_desc": (
            "نفس تخطيط Neovim: البحث يصفّي المجموعات، عمودان متساويان، كل سطر إجراء. "
            "استخدم أيقونة النسخ أو انقر السطر للأوامر؛ في النظرة العامة انسخ أو افتح الروابط."
        ),
        "search_placeholder": "تصفية الأقسام والأوامر…",
        "hint": (
            "اكتب كلمات لتضييق المجموعات (العنوان والوصف ونص الصفوف). "
            "انقر الصف أو أيقونة النسخ لنسخ السطر؛ للصفوف التي هي رابط فقط، النقر يفتح المقال."
        ),
        "overview_title": "نظرة عامة — روابط التوثيق",
        "overview_desc": (
            "كل صف يمثل مقالاً عن أمر. النسخ يضع الرابط في الحافظة؛ ابحث باسم الأداة."
        ),
        "table_row": "صف جدول",
    },
}


def _expand_md_links(s: str) -> str:
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s).strip()


def _normalize_heading(line: str) -> str:
    t = line.strip()
    t = re.sub(r"\*+", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return t.strip()


def _code_line_to_row(line: str) -> tuple[str, str, str] | None:
    s = line.rstrip()
    if not s.strip():
        return None
    main, _, comment = s.partition("#")
    main = main.rstrip()
    comment = comment.strip()
    title = _expand_md_links(main)
    if len(title) > 180:
        title = title[:177] + "…"
    copy = _expand_md_links(main).strip() or s.strip()
    sub = comment
    if not sub:
        m = re.search(r"(https?://[^\s)]+)", s)
        if m:
            sub = m.group(1)
    return (title, sub, copy)


def _prose_lines_to_rows(text: str, *, table_row_label: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s or s == "---":
            continue
        if s.startswith("|"):
            if _TABLE_SEP.match(s):
                continue
            t = _expand_md_links(s)
            rows.append((t[:180], table_row_label, t[:600]))
            continue
        if s.startswith("- "):
            t = _expand_md_links(s[2:])
            rows.append((t[:180], "", t))
            continue
        if s.startswith("####") or s.startswith("###"):
            n = _normalize_heading(s.lstrip("#"))
            rows.append((f"▸ {n}", "", n))
            continue
        m = re.match(r"^\[([^\]]+)\]\(([^)]+)\)\s*$", s)
        if m:
            rows.append((m.group(1), m.group(2), m.group(2)))
            continue
        if s.startswith("**") and s.endswith("**") and s.count("**") >= 2:
            n = _normalize_heading(s)
            rows.append((n, "", n))
            continue
        if len(s) > 1:
            t = _expand_md_links(s)
            rows.append((t[:180], "", t[:1200]))
    return rows


def _rows_from_section_body(body: str, *, table_row_label: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    pos = 0
    for m in _FENCE.finditer(body):
        if m.start() > pos:
            rows.extend(_prose_lines_to_rows(body[pos : m.start()], table_row_label=table_row_label))
        for cl in m.group(1).splitlines():
            r = _code_line_to_row(cl)
            if r:
                rows.append(r)
        pos = m.end()
    if pos < len(body):
        rows.extend(_prose_lines_to_rows(body[pos:], table_row_label=table_row_label))
    return rows


def _extract_preamble_links(preamble: str) -> list[tuple[str, str, str]]:
    """One row per [label](url) in the preamble tables — readable, copyable URLs."""
    rows: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)]+)\)", preamble):
        label = re.sub(r"\*+", "", m.group(1)).strip() or "link"
        url = m.group(2).strip()
        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        host = urlparse(url).netloc or url[:48]
        rows.append((label[:100], host, url))
        if len(rows) >= _PREAMBLE_MAX_LINKS:
            break
    return rows


def parse_desktop_cli_md(
    md: str,
    *,
    overview_title: str,
    overview_desc: str,
    table_row_label: str,
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """Split markdown into (group title, description, rows of title, subtitle, copy_text)."""
    md = md.strip()
    chunks = _SECTION_SPLIT.split(md)
    out: list[tuple[str, str, list[tuple[str, str, str]]]] = []
    preamble = chunks[0].strip() if chunks else ""
    if preamble:
        pr = _extract_preamble_links(preamble)
        if pr:
            out.append(
                (
                    overview_title,
                    overview_desc,
                    pr,
                ),
            )
    for chunk in chunks[1:]:
        if not chunk.strip():
            continue
        parts = chunk.split("\n", 1)
        head = parts[0].strip()
        body = parts[1] if len(parts) > 1 else ""
        title = _normalize_heading(head)
        desc = ""
        hm = re.search(r"\((https?://[^)]+)\)", head)
        if hm:
            desc = hm.group(1)
        rows = _rows_from_section_body(body, table_row_label=table_row_label)
        if not rows:
            continue
        out.append((title, desc, rows))
    return out


def _load_cli_locale_bundle() -> dict[str, dict[str, dict[str, str]]]:
    path = Path(__file__).with_name("desktop_cli_locale.json")
    if not path.is_file():
        return {"de": {"sections": {}, "subtitles": {}}, "ar": {"sections": {}, "subtitles": {}}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"de": {"sections": {}, "subtitles": {}}, "ar": {"sections": {}, "subtitles": {}}}
    for tgt in ("de", "ar"):
        raw.setdefault(tgt, {})
        raw[tgt].setdefault("sections", {})
        raw[tgt].setdefault("subtitles", {})
    return raw


def localize_cli_sections(
    sections: list[tuple[str, str, list[tuple[str, str, str]]]],
    lang: str,
    locale: dict[str, dict[str, dict[str, str]]],
    ui_en: dict[str, str],
) -> list[tuple[str, str, list[tuple[str, str, str]]]]:
    """Apply DE/AR strings from desktop_cli_locale.json; English UI chrome unchanged."""
    if lang == "en":
        return sections
    u = _CLI_UI.get(lang, _CLI_UI["en"])
    table_en = ui_en["table_row"]
    sec_map = locale.get(lang, {}).get("sections", {})
    sub_map = locale.get(lang, {}).get("subtitles", {})
    out: list[tuple[str, str, list[tuple[str, str, str]]]] = []
    overview_title_en = ui_en["overview_title"]
    for title, desc, rows in sections:
        if title == overview_title_en:
            new_title = u["overview_title"]
            new_desc = u["overview_desc"]
        else:
            new_title = sec_map.get(title, title)
            new_desc = desc
        new_rows: list[tuple[str, str, str]] = []
        for cmd, sub, clip in rows:
            new_sub = u["table_row"] if sub == table_en else sub_map.get(sub, sub)
            new_rows.append((cmd, new_sub, clip))
        out.append((new_title, new_desc, new_rows))
    return out


def _split_columns_document_order(
    sections: list[tuple[str, str, list[tuple[str, str, str]]]],
) -> tuple[list[tuple[str, str, list[tuple[str, str, str]]]], list[tuple[str, str, list[tuple[str, str, str]]]]]:
    left = [sections[i] for i in range(0, len(sections), 2)]
    right = [sections[i] for i in range(1, len(sections), 2)]
    return left, right


def _copy_cmd(text: str) -> None:
    if copy_plain_text_to_clipboard(text):
        emit_utility_toast("Copied to clipboard.", "info", timeout=3)
    else:
        emit_utility_toast("Could not copy to clipboard.", "error", timeout=3)


class DesktopCliReferencePage(Gtk.Box):
    """Terminal & CLI reference — same interaction model as the Neovim cheatsheet page."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, **kwargs)
        self.add_css_class("workstation-learn-colored-titles")
        self.set_margin_start(14)
        self.set_margin_end(14)
        self.set_margin_top(10)
        self.set_margin_bottom(18)

        self._lang = "en"
        self._search_targets: list[tuple[Gtk.Revealer, Adw.PreferencesGroup, str]] = []
        self._title_color_idx = 0
        self._intro: Adw.PreferencesGroup | None = None
        self._hint: Gtk.Label | None = None
        lang_group = Adw.PreferencesGroup()
        lang_group.add_css_class("bash-cheatsheet-group")
        self._lang_row = Adw.ComboRow()
        self._lang_row.set_model(Gtk.StringList.new(["English", "Deutsch", "العربية"]))
        self._lang_row.set_selected(0)
        lang_group.add(self._lang_row)
        self.append(lang_group)

        path = Path(__file__).with_name("desktop_cli_reference.md")
        if not path.is_file():
            self.append(
                Adw.StatusPage(
                    title="Reference missing",
                    description=f"Expected {path.name} next to the Learn CLI page module.",
                ),
            )
            self._apply_cli_lang_ui()
            self._lang_row.connect("notify::selected", self._on_cli_lang_selected)
            return

        raw = path.read_text(encoding="utf-8")
        u0 = _CLI_UI["en"]
        self._raw_sections = parse_desktop_cli_md(
            raw,
            overview_title=u0["overview_title"],
            overview_desc=u0["overview_desc"],
            table_row_label=u0["table_row"],
        )
        self._locale = _load_cli_locale_bundle()
        self._c1 = self._column()
        self._c2 = self._column()

        self._intro = Adw.PreferencesGroup()
        self._intro.add_css_class("bash-cheatsheet-group")
        self.append(self._intro)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        search_row.set_margin_start(4)
        search_row.set_margin_end(4)
        icon = Gtk.Image.new_from_icon_name("edit-find-symbolic")
        icon.set_valign(Gtk.Align.CENTER)
        self._search = Gtk.SearchEntry()
        self._search.set_hexpand(True)
        self._search.connect("notify::text", self._on_search_changed)
        search_row.append(icon)
        search_row.append(self._search)
        self.append(search_row)

        self._hint = Gtk.Label(xalign=0.0, wrap=True)
        self._hint.add_css_class("caption")
        self._hint.add_css_class("dim-label")
        self._hint.set_margin_start(8)
        self._hint.set_margin_end(8)
        self.append(self._hint)

        self._columns = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=22,
            vexpand=True,
            hexpand=True,
        )
        self._columns.set_homogeneous(True)
        self._columns.add_css_class("workstation-cli-columns")
        self._columns.append(self._c1)
        self._columns.append(self._c2)
        self.append(self._columns)

        self._rebuild_cli_columns()
        self._apply_cli_lang_ui()
        self._lang_row.connect("notify::selected", self._on_cli_lang_selected)

    def _on_cli_lang_selected(self, row: Adw.ComboRow, _pspec: GObject.ParamSpec) -> None:
        i = row.get_selected()
        if i < 0 or i >= len(_LANG_CODES):
            return
        lang = _LANG_CODES[i]
        if lang == self._lang:
            return
        self._lang = lang
        self._rebuild_cli_columns()
        self._apply_cli_lang_ui()

    def _rebuild_cli_columns(self) -> None:
        if not hasattr(self, "_raw_sections"):
            return
        for col in (self._c1, self._c2):
            while col.get_first_child() is not None:
                col.remove(col.get_first_child())
        self._search_targets.clear()
        self._title_color_idx = 0

        sections = localize_cli_sections(
            self._raw_sections,
            self._lang,
            self._locale,
            _CLI_UI["en"],
        )
        left, right = _split_columns_document_order(sections)
        for sec in left:
            self._append_section_group(self._c1, sec)
        for sec in right:
            self._append_section_group(self._c2, sec)

    def _apply_cli_lang_ui(self) -> None:
        u = _CLI_UI.get(self._lang, _CLI_UI["en"])
        self._lang_row.set_title(u["lang_row_title"])
        if self._intro is not None:
            self._intro.set_title(learn_colored_title(u["intro_title"], 0))
            self._intro.set_description(u["intro_desc"])
        if self._search is not None:
            self._search.set_placeholder_text(u["search_placeholder"])
        if self._hint is not None:
            self._hint.set_label(u["hint"])

    @staticmethod
    def _column() -> Gtk.Box:
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        col.add_css_class("workstation-cli-column")
        col.set_size_request(300, -1)
        return col

    def _on_search_changed(self, *_args: Any) -> None:
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        raw = self._search.get_text().strip().lower()
        parts = [p for p in raw.split() if p]
        for revealer, group, extra_search in self._search_targets:
            title = group.get_title() or ""
            desc = group.get_description() or ""
            blob = " ".join(
                " ".join((title, desc, extra_search)).lower().split(),
            )
            revealer.set_reveal_child(not parts or all(p in blob for p in parts))
        scroll_learn_search_to_first_hit(self._search_targets, has_query=bool(parts))

    def _append_group(
        self,
        col: Gtk.Box,
        group: Adw.PreferencesGroup,
        *,
        extra_search: str = "",
        raw_title: str | None = None,
    ) -> None:
        title = raw_title if raw_title is not None else (group.get_title() or "")
        if title:
            group.set_title(learn_colored_title(title, self._title_color_idx))
            self._title_color_idx += 1
        group.add_css_class("bash-cheatsheet-group")
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        outer.set_margin_bottom(12)
        revealer = Gtk.Revealer()
        revealer.set_child(group)
        revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        revealer.set_reveal_child(True)
        outer.append(revealer)
        col.append(outer)
        self._search_targets.append((revealer, group, extra_search))

    def _append_section_group(
        self,
        col: Gtk.Box,
        section: tuple[str, str, list[tuple[str, str, str]]],
    ) -> None:
        title, desc, rows = section
        safe_desc = GLib.markup_escape_text(desc) if desc else None
        g = Adw.PreferencesGroup(description=safe_desc)
        self._add_rows(g, rows)
        extra = " ".join(" ".join(r[:2]) for r in rows).lower()
        if len(extra) > 3000:
            extra = extra[:3000]
        self._append_group(col, g, extra_search=extra, raw_title=title)

    def _add_rows(self, group: Adw.PreferencesGroup, rows: list[tuple[str, str, str]]) -> None:
        for cmd, sub, clip in rows:
            row = Adw.ActionRow()
            row.set_use_markup(False)
            row.set_title(cmd)
            row.set_subtitle(sub or " ")
            row.set_activatable(True)
            row.add_css_class("numeric")
            row.set_margin_start(8)
            row.set_margin_end(8)
            row.set_margin_top(2)
            row.set_margin_bottom(2)

            def _on_act(
                _r: Adw.ActionRow,
                c: str = clip,
                t: str = cmd,
                s: str = sub,
            ) -> None:
                if c.startswith(("http://", "https://")):
                    with contextlib.suppress(GLib.Error):
                        Gio.AppInfo.launch_default_for_uri(c, None)
                    emit_utility_toast(
                        f"Opened: {t[:60]}{'…' if len(t) > 60 else ''}",
                        "info",
                        timeout=4,
                    )
                else:
                    _copy_cmd(c)
                    if s and not s.startswith("http"):
                        emit_utility_toast(
                            s[:140] + ("…" if len(s) > 140 else ""),
                            "info",
                            timeout=5,
                        )

            row.connect("activated", _on_act)

            copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.set_has_frame(False)
            copy_btn.add_css_class("flat")

            copy_btn.connect("clicked", lambda _b, c=clip: _copy_cmd(c))

            row.add_suffix(copy_btn)
            group.add(row)
