"""Linux FHS overview — expandable tree, colors, EN/DE/AR (Welcome / System Monitor)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, GObject, Gtk, Pango  # noqa: E402

from ui.widgets.workstation.workstation_learning_scroll import learn_colored_title  # noqa: E402

_LANG_CODES = ("en", "de", "ar")

_UI: dict[str, dict[str, str]] = {
    "en": {
        "lang_row_title": "Language",
        "intro_title": "Linux directory tree (FHS)",
        "intro_desc": (
            "The Filesystem Hierarchy Standard (FHS) describes the usual layout under /. "
            "Distributions mostly follow it; many merge /bin into /usr/bin and use a single /usr tree. "
            "Below is a deep tree with real paths, examples, and typical file names. "
            "Branches start expanded; you can collapse rows to focus. "
            "Use the language control for English, German, or Arabic (same structure and meaning)."
        ),
        "tree_title": "Directory tree",
        "tree_desc": (
            "Path (left) and purpose with concrete examples (right). "
            "Path colors group related areas (boot, devices, config, …). Arrows collapse or reopen subtrees."
        ),
        "col_path": "Path",
        "col_purpose": "Purpose (examples)",
    },
    "de": {
        "lang_row_title": "Sprache",
        "intro_title": "Linux-Verzeichnisbaum (FHS)",
        "intro_desc": (
            "Der Filesystem Hierarchy Standard (FHS) beschreibt die übliche Struktur unter /. "
            "Distributionen folgen ihm größtenteils; viele führen /bin mit /usr/bin zusammen und nutzen einen /usr-Baum. "
            "Unten steht ein tiefer Baum mit echten Pfaden, Beispielen und typischen Dateinamen. "
            "Zweige sind zunächst aufgeklappt; du kannst Zeilen zuklappen, um dich zu konzentrieren. "
            "Über die Sprachauswahl erhältst du Englisch, Deutsch oder Arabisch (gleiche Struktur und Bedeutung)."
        ),
        "tree_title": "Verzeichnisbaum",
        "tree_desc": (
            "Pfad (links) und Zweck mit konkreten Beispielen (rechts). "
            "Pfadfarben gruppieren zusammengehörige Bereiche (Boot, Geräte, Konfiguration, …). "
            "Pfeile klappen Teilbäume zu oder wieder auf."
        ),
        "col_path": "Pfad",
        "col_purpose": "Zweck (Beispiele)",
    },
    "ar": {
        "lang_row_title": "اللغة",
        "intro_title": "شجرة مجلدات Linux (معيار FHS)",
        "intro_desc": (
            "يصف معيار تسلسل هيكل نظام الملفات (FHS) التخطيط المعتاد تحت /. "
            "معظم التوزيعات تتبعه؛ وكثير منها يدمج ‎/bin‎ في ‎/usr/bin‎ ويستخدم شجرة ‎/usr‎ واحدة. "
            "فيما يلي شجرة عميقة بمسارات حقيقية وأمثلة وأسماء ملفات نموذجية. "
            "الفروع مفتوحة في البداية؛ يمكنك طي الصفوف للتركيز. "
            "عبر اختيار اللغة تحصل على نفس المحتوى بالإنجليزية أو الألمانية أو العربية."
        ),
        "tree_title": "شجرة المجلدات",
        "tree_desc": (
            "المسار (يسارًا) والغرض مع أمثلة عملية (يمينًا). "
            "ألوان المسار تجمّع المناطق ذات الصلة (الإقلاع، الأجهزة، الإعدادات، …). "
            "الأسهم تطوي الفروع أو تعيد فتحها."
        ),
        "col_path": "المسار",
        "col_purpose": "الغرض (أمثلة)",
    },
}

# Path colors: tuned for dark vs light window (Adw.StyleManager.get_dark()).
_PATH_FG_DARK: dict[str, str] = {
    "root": "#f5d565",
    "bin": "#7dd3fc",
    "sbin": "#93c5fd",
    "examples": "#bef264",
    "boot": "#fdba74",
    "dev": "#e9d5ff",
    "etc": "#bbf7d0",
    "home": "#5eead4",
    "lib": "#93c5fd",
    "lib64": "#93c5fd",
    "lost": "#cbd5e1",
    "media": "#cbd5e1",
    "mnt": "#cbd5e1",
    "opt": "#fcd34d",
    "proc": "#fca5a5",
    "root_home": "#e2e8f0",
    "run": "#f5d0fe",
    "srv": "#fdba74",
    "sys": "#fca5a5",
    "tmp": "#fcd34d",
    "usr": "#7dd3fc",
    "var": "#fda4af",
    "misc": "#99f6e4",
}

_PATH_FG_LIGHT: dict[str, str] = {
    "root": "#a16207",
    "bin": "#0369a1",
    "sbin": "#075985",
    "examples": "#3f6212",
    "boot": "#c2410c",
    "dev": "#6d28d9",
    "etc": "#166534",
    "home": "#0f766e",
    "lib": "#1d4ed8",
    "lib64": "#1d4ed8",
    "lost": "#475569",
    "media": "#475569",
    "mnt": "#475569",
    "opt": "#a16207",
    "proc": "#b91c1c",
    "root_home": "#334155",
    "run": "#86198f",
    "srv": "#c2410c",
    "sys": "#b91c1c",
    "tmp": "#a16207",
    "usr": "#0369a1",
    "var": "#9f1239",
    "misc": "#0f766e",
}

_FHS_TREE_FONT = "Calibri, Carlito, Arial, Liberation Sans, DejaVu Sans, sans-serif 16px"


def _load_fhs_rows() -> list[dict[str, str]]:
    path = Path(__file__).with_name("linux_fhs_lang.json")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        msg = "linux_fhs_lang.json must be a list of row objects"
        raise TypeError(msg)
    return raw


_FHS_ROWS: list[dict[str, str]] = _load_fhs_rows()


def _fill_tree_store(store: Gtk.TreeStore, lang: str) -> None:
    """Populate FHS-style hierarchy: path, localized purpose, section id for coloring."""

    if lang not in _LANG_CODES:
        lang = "en"

    rows = _FHS_ROWS
    row_iter = iter(rows)

    def take(path: str) -> dict[str, str]:
        row = next(row_iter)
        got = row.get("path")
        if got != path:
            msg = f"FHS bundle out of sync: expected {path!r}, got {got!r}"
            raise RuntimeError(msg)
        return row

    def a(parent: Gtk.TreeIter | None, path: str, section: str) -> Gtk.TreeIter:
        r = take(path)
        purpose = r.get(lang) or r["en"]
        return store.append(parent, [path, purpose, section])

    root = a(None, "/", "root")
    bin_ = a(root, "/bin", "bin")
    a(bin_, "(examples)", "examples")
    sbin = a(root, "/sbin", "sbin")
    a(sbin, "(examples)", "examples")
    boot = a(root, "/boot", "boot")
    a(boot, "/boot/efi", "boot")
    a(boot, "/boot/grub2", "boot")
    a(boot, "/boot/initramfs-*.img", "boot")
    a(boot, "/boot/vmlinuz-*", "boot")
    dev = a(root, "/dev", "dev")
    a(dev, "/dev/sd*", "dev")
    a(dev, "/dev/tty*", "dev")
    a(dev, "/dev/pts/", "dev")
    a(dev, "/dev/null", "dev")
    a(dev, "/dev/zero", "dev")
    a(dev, "/dev/urandom", "dev")
    a(dev, "/dev/random", "dev")
    etc = a(root, "/etc", "etc")
    a(etc, "/etc/fstab", "etc")
    a(etc, "/etc/hosts", "etc")
    a(etc, "/etc/os-release", "etc")
    a(etc, "/etc/passwd", "etc")
    a(etc, "/etc/shadow", "etc")
    a(etc, "/etc/group", "etc")
    a(etc, "/etc/sudoers + /etc/sudoers.d/", "etc")
    a(etc, "/etc/ssh/", "etc")
    a(etc, "/etc/ssl/certs/", "etc")
    a(etc, "/etc/systemd/system/", "etc")
    a(etc, "/etc/systemd/user/", "etc")
    a(etc, "/etc/default/", "etc")
    a(etc, "/etc/yum.repos.d/", "etc")
    a(etc, "/etc/apt/", "etc")
    a(etc, "/etc/pam.d/", "etc")
    a(etc, "/etc/environment", "etc")
    home = a(root, "/home", "home")
    a(home, "/home/<user>/", "home")
    a(home, "/home/<user>/.config/", "home")
    a(home, "/home/<user>/.local/share/", "home")
    a(home, "/home/<user>/.cache/", "home")
    a(home, "/home/<user>/Desktop …", "home")
    lib = a(root, "/lib", "lib")
    a(lib, "/lib/modules/$(uname -r)/", "lib")
    a(lib, "/lib/systemd/", "lib")
    a(root, "/lib64", "lib64")
    a(root, "/lost+found", "lost")
    a(root, "/media", "media")
    a(root, "/mnt", "mnt")
    opt = a(root, "/opt", "opt")
    a(opt, "/opt/<vendor>/<app>/", "opt")
    proc = a(root, "/proc", "proc")
    a(proc, "/proc/cpuinfo", "proc")
    a(proc, "/proc/meminfo", "proc")
    a(proc, "/proc/version", "proc")
    a(proc, "/proc/uptime", "proc")
    a(proc, "/proc/self", "proc")
    a(proc, "/proc/sys/", "proc")
    a(proc, "/proc/<pid>/", "proc")
    a(root, "/root", "root_home")
    run = a(root, "/run", "run")
    a(run, "/run/systemd/", "run")
    a(run, "/run/user/<uid>/", "run")
    a(run, "/run/lock/", "run")
    srv = a(root, "/srv", "srv")
    a(srv, "/srv/www/", "srv")
    sys = a(root, "/sys", "sys")
    a(sys, "/sys/class/", "sys")
    a(sys, "/sys/block/", "sys")
    a(sys, "/sys/devices/", "sys")
    tmpd = a(root, "/tmp", "tmp")
    a(tmpd, "/tmp/systemd-private-*/", "tmp")
    usr = a(root, "/usr", "usr")
    ub = a(usr, "/usr/bin", "usr")
    a(ub, "(examples)", "examples")
    us = a(usr, "/usr/sbin", "usr")
    a(us, "(examples)", "examples")
    ul = a(usr, "/usr/lib", "usr")
    a(ul, "/usr/lib/systemd/system/", "usr")
    a(ul, "/usr/libexec/", "usr")
    a(ul, "/usr/lib64/", "usr")
    a(usr, "/usr/include", "usr")
    uloc = a(usr, "/usr/local", "usr")
    a(uloc, "/usr/local/bin", "usr")
    a(uloc, "/usr/local/etc", "usr")
    ush = a(usr, "/usr/share", "usr")
    a(ush, "/usr/share/man", "usr")
    a(ush, "/usr/share/doc", "usr")
    a(ush, "/usr/share/applications", "usr")
    a(ush, "/usr/share/icons", "usr")
    a(ush, "/usr/share/locale", "usr")
    a(ush, "/usr/share/mime", "usr")
    a(ush, "/usr/share/fonts", "usr")
    a(usr, "/usr/src", "usr")
    var = a(root, "/var", "var")
    vlog = a(var, "/var/log", "var")
    a(vlog, "/var/log/messages or syslog", "var")
    a(vlog, "/var/log/journal/", "var")
    a(vlog, "/var/log/audit/audit.log", "var")
    a(vlog, "/var/log/dnf.rpm.log", "var")
    vcache = a(var, "/var/cache", "var")
    a(vcache, "/var/cache/dnf", "var")
    a(vcache, "/var/cache/apt/archives", "var")
    a(vcache, "/var/cache/flatpak", "var")
    vlib = a(var, "/var/lib", "var")
    a(vlib, "/var/lib/rpm", "var")
    a(vlib, "/var/lib/dpkg", "var")
    a(vlib, "/var/lib/systemd", "var")
    a(vlib, "/var/lib/docker or /var/lib/containers", "var")
    a(vlib, "/var/lib/postgresql", "var")
    a(vlib, "/var/lib/libvirt", "var")
    vsp = a(var, "/var/spool", "var")
    a(vsp, "/var/spool/cron", "var")
    a(var, "/var/tmp", "var")
    a(var, "/var/www", "var")

    # Ensure bundle length matches tree walk
    try:
        next(row_iter)
    except StopIteration:
        return
    msg = "linux_fhs_lang.json has extra rows after tree build"
    raise RuntimeError(msg)


def _cell_path_fg(
    _col: Gtk.TreeViewColumn,
    cell: Gtk.CellRenderer,
    model: Gtk.TreeModel,
    iter_: Gtk.TreeIter,
    *_user_data: Any,
) -> None:
    dark = Adw.StyleManager.get_default().get_dark()
    palette = _PATH_FG_DARK if dark else _PATH_FG_LIGHT
    sec = str(model.get_value(iter_, 2))
    fg = palette.get(sec, palette["misc"])
    cell.set_property("foreground", fg)
    cell.set_property("foreground-set", True)


def _cell_desc_fg(
    _col: Gtk.TreeViewColumn,
    cell: Gtk.CellRenderer,
    model: Gtk.TreeModel,
    iter_: Gtk.TreeIter,
    *_user_data: Any,
) -> None:
    dark = Adw.StyleManager.get_default().get_dark()
    # Single high-contrast body color (section tint on paths only).
    fg = "#e8edf4" if dark else "#1e293b"
    cell.set_property("foreground", fg)
    cell.set_property("foreground-set", True)


class LinuxFilesystemPage(Gtk.Box):
    """Expandable tree of standard Linux directories (FHS-style), colored paths, EN/DE/AR."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, **kwargs)
        self.add_css_class("workstation-learn-colored-titles")
        self.set_margin_start(18)
        self.set_margin_end(18)
        self.set_margin_top(12)
        self.set_margin_bottom(18)

        self._lang = "en"

        lang_group = Adw.PreferencesGroup()
        self._lang_row = Adw.ComboRow()
        self._lang_row.set_model(Gtk.StringList.new(["English", "Deutsch", "العربية"]))
        self._lang_row.set_selected(0)
        lang_group.add(self._lang_row)
        self.append(lang_group)

        self._intro = Adw.PreferencesGroup()
        self.append(self._intro)

        self._tree_group = Adw.PreferencesGroup()
        self.append(self._tree_group)

        store = Gtk.TreeStore(GObject.TYPE_STRING, GObject.TYPE_STRING, GObject.TYPE_STRING)
        self._store = store
        _fill_tree_store(store, self._lang)

        tree = Gtk.TreeView(model=store)
        self._tree = tree
        tree.set_headers_visible(True)
        tree.set_enable_tree_lines(True)
        tree.add_css_class("workstation-fhs-tree")

        font_desc = Pango.FontDescription.from_string(_FHS_TREE_FONT)

        r0 = Gtk.CellRendererText()
        r0.set_padding(8, 4)
        r0.set_property("font-desc", font_desc)
        r0.set_property("weight", Pango.Weight.SEMIBOLD)
        c0 = Gtk.TreeViewColumn(title="", cell_renderer=r0, text=0)
        c0.set_cell_data_func(r0, _cell_path_fg)
        c0.set_resizable(True)
        c0.set_min_width(200)
        tree.append_column(c0)

        r1 = Gtk.CellRendererText()
        r1.set_padding(8, 4)
        r1.set_property("font-desc", font_desc)
        r1.set_property("weight", Pango.Weight.NORMAL)
        r1.props.wrap_mode = Pango.WrapMode.WORD_CHAR
        r1.props.wrap_width = 700
        c1 = Gtk.TreeViewColumn(title="", cell_renderer=r1, text=1)
        c1.set_cell_data_func(r1, _cell_desc_fg)
        c1.set_expand(True)
        tree.append_column(c1)

        self._col_path = c0
        self._col_purpose = c1

        tree.expand_all()

        sw = Gtk.ScrolledWindow(
            hexpand=True,
            vexpand=True,
            min_content_height=560,
            hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        sw.set_child(tree)
        self._tree_group.add(sw)

        self._apply_lang_ui(self._lang)
        self._lang_row.connect("notify::selected", self._on_lang_selected)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: tree.queue_draw())

    def _on_lang_selected(self, row: Adw.ComboRow, _pspec: GObject.ParamSpec) -> None:
        i = row.get_selected()
        if i < 0 or i >= len(_LANG_CODES):
            return
        lang = _LANG_CODES[i]
        if lang == self._lang:
            return
        self._lang = lang
        self._store.clear()
        _fill_tree_store(self._store, lang)
        self._tree.expand_all()
        self._apply_lang_ui(lang)

    def _apply_lang_ui(self, lang: str) -> None:
        u = _UI.get(lang, _UI["en"])
        self._lang_row.set_title(u["lang_row_title"])
        self._intro.set_title(learn_colored_title(u["intro_title"], 0))
        self._intro.set_description(u["intro_desc"])
        self._tree_group.set_title(learn_colored_title(u["tree_title"], 1))
        self._tree_group.set_description(u["tree_desc"])
        self._col_path.set_title(u["col_path"])
        self._col_purpose.set_title(u["col_purpose"])
