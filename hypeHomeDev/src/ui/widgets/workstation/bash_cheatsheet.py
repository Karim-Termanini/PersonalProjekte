"""3-column Bash scripting cheatsheet for Workstation Learn hub."""

from __future__ import annotations

import logging
from typing import Any

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk, Pango  # noqa: E402

from ui.utility_feedback import emit_utility_toast  # noqa: E402
from ui.widgets.workstation.bash_cheatsheet_i18n import _LANG_CODES, bash_ui  # noqa: E402
from ui.widgets.workstation.nav_helper import copy_plain_text_to_clipboard  # noqa: E402
from ui.widgets.workstation.workstation_learning_scroll import learn_colored_title, scroll_learn_search_to_first_hit  # noqa: E402

log = logging.getLogger(__name__)


def _copy_cmd(cmd: str) -> None:
    if copy_plain_text_to_clipboard(cmd):
        emit_utility_toast("Copied to clipboard.", "info", timeout=3)
    else:
        emit_utility_toast("Could not copy to clipboard.", "error")


class BashCheatsheetPage(Gtk.Box):
    """Full devhints-style Bash reference in three scroll-width columns."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=14, **kwargs)
        self.add_css_class("workstation-learn-colored-titles")
        self.set_margin_start(14)
        self.set_margin_end(14)
        self.set_margin_top(10)
        self.set_margin_bottom(18)

        self._search_targets: list[tuple[Gtk.Revealer, str]] = []
        self._title_color_idx = 0

        self._lang = "en"

        # Language selector
        lang_group = Adw.PreferencesGroup()
        lang_group.add_css_class("bash-cheatsheet-group")
        self._lang_row = Adw.ComboRow()
        self._lang_row.set_model(Gtk.StringList.new(["English", "Deutsch", "العربية"]))
        self._lang_row.set_selected(0)
        lang_group.add(self._lang_row)
        self.append(lang_group)

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

        self._columns = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=28,
            vexpand=False,
            hexpand=True,
        )
        self._columns.set_valign(Gtk.Align.START)

        self._col1 = self._column()
        self._col2 = self._column()
        self._columns.append(self._col1)
        self._columns.append(self._col2)

        self.append(search_row)
        self.append(self._columns)

        self._build_columns()
        self._apply_lang_ui(self._lang)
        self._lang_row.connect("notify::selected", self._on_lang_selected)

    def _on_lang_selected(self, row: Adw.ComboRow, _pspec: Any) -> None:
        i = row.get_selected()
        if i < 0 or i >= len(_LANG_CODES):
            return
        lang = _LANG_CODES[i]
        if lang == self._lang:
            return
        self._lang = lang
        # Clear columns
        while self._col1.get_first_child():
            self._col1.remove(self._col1.get_first_child())
        while self._col2.get_first_child():
            self._col2.remove(self._col2.get_first_child())
        self._search_targets.clear()
        self._title_color_idx = 0
        self._build_columns()
        self._apply_lang_ui(self._lang)

    def _apply_lang_ui(self, lang: str) -> None:
        u = bash_ui(lang)
        self._lang_row.set_title(u["lang_row_title"])
        self._search_lbl.set_label(u["search_label"])
        self._search.set_placeholder_text(u["search_placeholder"])

    def _build_columns(self) -> None:
        self._build_column_1(self._col1)
        self._build_column_2(self._col2)

    def _on_search_changed(self, *_args: Any) -> None:
        self._apply_search_filter()

    def _apply_search_filter(self) -> None:
        raw = self._search.get_text().strip().lower()
        parts = [p for p in raw.split() if p]
        for revealer, blob in self._search_targets:
            revealer.set_reveal_child(not parts or all(p in blob for p in parts))
        scroll_learn_search_to_first_hit(self._search_targets, has_query=bool(parts))

    def _append_group(
        self,
        col: Gtk.Box,
        group: Adw.PreferencesGroup,
        *,
        extra_search: str = "",
    ) -> None:
        title = group.get_title() or ""
        desc = group.get_description() or ""
        blob = " ".join((" ".join((title, desc, extra_search))).lower().split())

        if title:
            group.set_title(learn_colored_title(title, self._title_color_idx))
            self._title_color_idx += 1

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.set_margin_start(10)
        outer.set_margin_end(10)
        outer.set_margin_bottom(12)

        group.add_css_class("bash-cheatsheet-group")

        revealer = Gtk.Revealer()
        revealer.set_child(group)
        revealer.set_transition_type(Gtk.RevealerTransitionType.NONE)
        revealer.set_reveal_child(True)
        outer.append(revealer)
        col.append(outer)
        self._search_targets.append((revealer, blob))

    @staticmethod
    def _column(width_multiplier: float = 1.0) -> Gtk.Box:
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        return col

    def _build_column_1(self, col: Gtk.Box) -> None:
        u = bash_ui(self._lang)
        intro = Adw.PreferencesGroup(
            title=u["intro_title"],
            description=u["intro_desc"],
        )
        self._add_link_row(intro, "Learn bash in y minutes", "https://learnxinyminutes.com/docs/bash/")
        self._add_link_row(intro, "Bash Guide", "https://mywiki.wooledge.org/BashGuide")
        self._add_link_row(intro, "Bash Hackers Wiki", "https://wiki.bash-hackers.org/")
        self._append_group(col,intro)

        example = Adw.PreferencesGroup(title=u["example_title"])
        self._add_code_block(
            example,
            '#!/usr/bin/env bash\n\nname="John"\necho "Hello $name!"',
        )
        self._append_group(col,example)

        variables = Adw.PreferencesGroup(title=u["variables_title"])
        self._add_code_block(
            variables,
            'name="John"\necho $name  # see below\necho "$name"\necho "${name}!"',
        )
        self._add_text_row(
            variables,
            u["variables_desc"],
        )
        self._add_code_block(
            variables,
            'wildcard="*.txt"\noptions="iv"\ncp -$options $wildcard /tmp',
        )
        self._append_group(col,variables)

        quotes = Adw.PreferencesGroup(title=u["quotes_title"])
        self._add_code_block(
            quotes,
            'name="John"\necho "Hi $name"  #=> Hi John\necho \'Hi $name\'  #=> Hi $name',
        )
        self._append_group(col,quotes)

        execution = Adw.PreferencesGroup(title=u["execution_title"])
        self._add_code_block(
            execution,
            'echo "I\'m in $(pwd)"\necho "I\'m in `pwd`"  # obsolescent\n# Same',
        )
        self._add_text_row(execution, u["execution_footer"])
        self._append_group(col,execution)

        cond_exec = Adw.PreferencesGroup(title=u["cond_exec_title"])
        self._add_code_block(
            cond_exec,
            'git commit && git push\ngit commit || echo "Commit failed"',
        )
        self._append_group(col,cond_exec)

        functions = Adw.PreferencesGroup(title=u["functions_title"])
        self._add_code_block(
            functions,
            'get_name() {\n  echo "John"\n}\n\necho "You are $(get_name)"',
        )
        self._add_text_row(functions, u["functions_footer"])
        self._append_group(col,functions)

        conditionals = Adw.PreferencesGroup(title=u["conditionals_title"])
        self._add_code_block(
            conditionals,
            'if [[ -z "$string" ]]; then\n  echo "String is empty"\nelif [[ -n "$string" ]]; then\n  echo "String is not empty"\nfi',
        )
        self._add_text_row(conditionals, u["conditionals_footer"])
        self._append_group(col,conditionals)

        strict = Adw.PreferencesGroup(title=u["strict_title"])
        self._add_code_block(strict, "set -euo pipefail\nIFS=$'\\n\\t'")
        self._add_text_row(strict, u["strict_footer"])
        self._append_group(col,strict)

        brace = Adw.PreferencesGroup(title=u["brace_title"])
        self._add_code_block(brace, "echo {A,B}.js")
        self._add_table_row(brace, "{A,B}", "Same as A B")
        self._add_table_row(brace, "{A,B}.js", "Same as A.js B.js")
        self._add_table_row(brace, "{1..5}", "Same as 1 2 3 4 5")
        self._add_table_row(brace, "{{1..3},{7..9}}", "Same as 1 2 3 7 8 9")
        self._add_text_row(brace, u["brace_footer"])
        self._append_group(col, brace)

        arr = Adw.PreferencesGroup(title=u["arrays_def_title"], description=u["arrays_def_desc"])
        self._add_code_block(
            arr,
            "Fruits=('Apple' 'Banana' 'Orange')\nFruits[0]=\"Apple\"\nFruits[1]=\"Banana\"\nFruits[2]=\"Orange\"",
        )
        self._append_group(col, arr)

        arrw = Adw.PreferencesGroup(title=u["arrays_work_title"], description=u["arrays_work_desc"])
        self._add_code_block(
            arrw,
            'echo "${Fruits[0]}"           # Element #0\necho "${Fruits[-1]}"          # Last element\n'
            'echo "${Fruits[@]}"           # All elements, space-separated\n'
            'echo "${#Fruits[@]}"          # Number of elements\n'
            'echo "${#Fruits}"             # String length of the 1st element\n'
            'echo "${#Fruits[3]}"          # String length of the Nth element\n'
            'echo "${Fruits[@]:3:2}"       # Range (from position 3, length 2)\n'
            'echo "${!Fruits[@]}"          # Keys of all elements, space-separated',
        )
        self._append_group(col, arrw)

        arro = Adw.PreferencesGroup(title=u["arrays_ops_title"], description=u["arrays_ops_desc"])
        self._add_code_block(
            arro,
            'Fruits=("${Fruits[@]}" "Watermelon")    # Push\nFruits+=(\'Watermelon\')                  # Also Push\n'
            'Fruits=( "${Fruits[@]/Ap*/}" )          # Remove by regex match\nunset Fruits[2]                         # Remove one item\n'
            'Fruits=("${Fruits[@]}")                 # Duplicate\n'
            'Fruits=("${Fruits[@]}" "${Veggies[@]}") # Concatenate\n'
            'words=($(< datafile))                   # From file (split by IFS)',
        )
        self._append_group(col, arro)

        arri = Adw.PreferencesGroup(title=u["arrays_iter_title"], description=u["arrays_iter_desc"])
        self._add_code_block(
            arri,
            'for i in "${arrayName[@]}"; do\n  echo "$i"\ndone',
        )
        self._append_group(col, arri)

        dict_def = Adw.PreferencesGroup(title=u["dict_def_title"], description=u["dict_def_desc"])
        self._add_code_block(
            dict_def,
            'declare -A sounds\nsounds[dog]="bark"\nsounds[cow]="moo"\n'
            'sounds[bird]="tweet"\nsounds[wolf]="howl"',
        )
        self._add_text_row(dict_def, "Associative array (dictionary).")
        self._append_group(col, dict_def)

        dict_w = Adw.PreferencesGroup(title=u["dict_work_title"], description=u["dict_work_desc"])
        self._add_code_block(
            dict_w,
            'echo "${sounds[dog]}" # Dog\'s sound\necho "${sounds[@]}"   # All values\n'
            'echo "${!sounds[@]}"  # All keys\necho "${#sounds[@]}"  # Number of elements\n'
            "unset sounds[dog]     # Delete dog",
        )
        self._append_group(col, dict_w)

        dict_i = Adw.PreferencesGroup(title=u["dict_iter_title"], description=u["dict_iter_desc"])
        self._add_code_block(
            dict_i,
            'for val in "${sounds[@]}"; do\n  echo "$val"\ndone',
        )
        self._add_code_block(
            dict_i,
            'for key in "${!sounds[@]}"; do\n  echo "$key"\ndone',
        )
        self._append_group(col, dict_i)

        misc = Adw.PreferencesGroup(title=u["misc_num_title"], description=u["misc_num_desc"])
        self._add_code_block(
            misc,
            "$((a + 200))      # Add 200 to $a\n$(($RANDOM%200))  # Random number 0..199\n"
            "declare -i count  # Declare as integer\ncount+=1          # Increment",
        )
        self._append_group(col, misc)

        sub = Adw.PreferencesGroup(title=u["subshells_title"], description=u["subshells_desc"])
        self._add_code_block(
            sub,
            '(cd somedir; echo "I\'m now in $PWD")\npwd # still in first directory',
        )
        self._append_group(col, sub)

        redir = Adw.PreferencesGroup(title=u["redir_title"], description=u["redir_desc"])
        self._add_code_block(
            redir,
            'python hello.py > output.txt\npython hello.py >> output.txt\npython hello.py 2> error.log\n'
            "python hello.py 2>&1\npython hello.py 2>/dev/null\n"
            "python hello.py >output.txt 2>&1   # same as &>\npython hello.py &>/dev/null\n"
            'echo "$0: warning: too many users" >&2\npython hello.py < foo.txt\n'
            "diff <(ls -r) <(ls)",
        )
        self._append_group(col, redir)

        inspect = Adw.PreferencesGroup(title=u["inspect_title"], description=u["inspect_desc"])
        self._add_code_block(inspect, 'command -V cd\n#=> "cd is a function/alias/whatever"')
        self._append_group(col, inspect)

        trap = Adw.PreferencesGroup(title=u["trap_title"], description=u["trap_desc"])
        self._add_code_block(trap, "trap 'echo Error at about $LINENO' ERR")
        self._add_code_block(
            trap,
            'traperr() {\n  echo "ERROR: ${BASH_SOURCE[1]} at about ${BASH_LINENO[0]}"\n}\n\n'
            "set -o errtrace\ntrap traperr ERR",
        )
        self._append_group(col, trap)

        case = Adw.PreferencesGroup(title=u["case_title"], description=u["case_desc"])
        self._add_code_block(
            case,
            'case "$1" in\n  start | up)\n    vagrant up\n    ;;\n\n  *)\n    echo "Usage: $0 {start|stop|ssh}"\n    ;;\nesac',
        )
        self._append_group(col, case)

        hist_s = Adw.PreferencesGroup(title=u["hist_slices_title"], description=u["hist_slices_desc"])
        self._add_table_row(hist_s, "!!:n", "Nth token from most recent command (0 = command; 1 = first arg)")
        self._add_table_row(hist_s, "!^", "First argument from most recent command")
        self._add_table_row(hist_s, "!$", "Last token from most recent command")
        self._add_table_row(hist_s, "!!:n-m", "Range of tokens from most recent command")
        self._add_table_row(hist_s, "!!:n-$", "Nth token to last from most recent command")
        self._add_text_row(
            hist_s,
            "!! can be replaced with any valid expansion (e.g. !cat, !-2, !42).",
        )
        self._append_group(col, hist_s)

        src_rel = Adw.PreferencesGroup(title=u["src_rel_title"], description=u["src_rel_desc"])
        self._add_code_block(src_rel, 'source "${0%/*}/../share/foo.sh"')
        self._append_group(col,src_rel)

        pr = Adw.PreferencesGroup(title=u["printf_title"], description=u["printf_desc"])
        self._add_code_block(
            pr,
            'printf "Hello %s, I\'m %s" Sven Olga\n#=> "Hello Sven, I\'m Olga"\n\n'
            'printf "1 + 1 = %d" 2\nprintf "This is how you print a float: %f" 2\n\n'
            "printf '%s\\n' '#!/bin/bash' 'echo hello' >file\n"
            "printf '%i+%i=%i\\n' 1 2 3  4 5 9",
        )
        self._append_group(col,pr)

        tr = Adw.PreferencesGroup(title=u["tr_title"], description=u["tr_desc"])
        self._add_table_row(tr, "-c", "Operations apply to characters not in the given set")
        self._add_table_row(tr, "-d", "Delete characters")
        self._add_table_row(tr, "-s", "Replace repeated characters with single occurrence")
        self._add_table_row(tr, "-t", "Truncates")
        self._add_table_row(tr, "[:upper:]", "All upper case letters")
        self._add_table_row(tr, "[:lower:]", "All lower case letters")
        self._add_table_row(tr, "[:digit:]", "All digits")
        self._add_table_row(tr, "[:space:]", "All whitespace")
        self._add_table_row(tr, "[:alpha:]", "All letters")
        self._add_table_row(tr, "[:alnum:]", "All letters and digits")
        self._add_code_block(
            tr,
            'echo "Welcome To Devhints" | tr \'[:lower:]\' \'[:upper:]\'\n# WELCOME TO DEVHINTS',
        )
        self._append_group(col,tr)

        dir_scr = Adw.PreferencesGroup(title=u["dir_scr_title"], description=u["dir_scr_desc"])
        self._add_code_block(dir_scr, "dir=${0%/*}")
        self._append_group(col,dir_scr)

        getopt = Adw.PreferencesGroup(title=u["getopt_title"], description=u["getopt_desc"])
        self._add_code_block(
            getopt,
            'while [[ "$1" =~ ^- && ! "$1" == "--" ]]; do case $1 in\n'
            "  -V | --version )\n    echo \"$version\"\n    exit\n    ;;\n"
            "  -s | --string )\n    shift; string=$1\n    ;;\n"
            "  -f | --flag )\n    flag=1\n    ;;\nesac; shift; done\n"
            'if [[ "$1" == \'--\' ]]; then shift; fi',
        )
        self._append_group(col,getopt)

        here = Adw.PreferencesGroup(title=u["heredoc_title"], description=u["heredoc_desc"])
        self._add_code_block(
            here,
            "cat <<END\nhello world\nEND",
        )
        self._add_text_row(here, "Heredoc: a section of source treated as a file. See Bash Reference Manual.")
        self._add_code_block(
            here,
            'tr \'[:lower:]\' \'[:upper:]\' <<< "Will be uppercased, even $variable"',
        )
        self._add_text_row(here, "Herestring: string as stdin. See Bash Reference Manual.")
        self._append_group(col,here)

        procsub = Adw.PreferencesGroup(title=u["procsub_title"], description=u["procsub_desc"])
        self._add_code_block(
            procsub,
            "# loop on myfunc output lines\nwhile read -r line; do\n  echo \"$line\"\ndone < <(myfunc)",
        )
        self._add_code_block(
            procsub,
            '# compare content of two folders\ndiff <(ls "$dir1") <(ls "$dir2")',
        )
        self._add_text_row(procsub, "Process substitution: command I/O treated as a file. See Bash Reference Manual.")
        self._append_group(col,procsub)

        read_in = Adw.PreferencesGroup(title=u["read_in_title"], description=u["read_in_desc"])
        self._add_code_block(
            read_in,
            'echo -n "Proceed? [y/n]: "\nread -r ans\necho "$ans"',
        )
        self._add_text_row(read_in, "The -r option disables legacy backslash behavior.")
        self._add_code_block(read_in, "read -n 1 ans    # Just one character")
        self._append_group(col,read_in)

        spec = Adw.PreferencesGroup(title=u["spec_vars_title"])
        self._add_table_row(spec, "$?", "Exit status of last task")
        self._add_table_row(spec, "$!", "PID of last background task")
        self._add_table_row(spec, "$$", "PID of shell")
        self._add_table_row(spec, "$0", "Filename of the shell script")
        self._add_table_row(spec, "$_", "Last argument of the previous command")
        self._add_table_row(spec, "${PIPESTATUS[n]}", "Return value of piped commands (array)")
        self._add_text_row(spec, "See: Special parameters")
        self._append_group(col,spec)

        prevdir = Adw.PreferencesGroup(title=u["prev_dir_title"], description=u["prev_dir_desc"])
        self._add_code_block(
            prevdir,
            "pwd # /home/user/foo\ncd bar/\npwd # /home/user/foo/bar\ncd -\npwd # /home/user/foo",
        )
        self._append_group(col,prevdir)

        chk = Adw.PreferencesGroup(title=u["check_res_title"], description=u["check_res_desc"])
        self._add_code_block(
            chk,
            'if ping -c 1 google.com; then\n  echo "It appears you have a working internet connection"\nfi',
        )
        self._append_group(col,chk)

        grepchk = Adw.PreferencesGroup(title=u["grep_chk_title"], description=u["grep_chk_desc"])
        self._add_code_block(
            grepchk,
            "if grep -q 'foo' ~/.bash_history; then\n  echo \"You appear to have typed 'foo' in the past\"\nfi",
        )
        self._append_group(col,grepchk)

    def _build_column_2(self, col: Gtk.Box) -> None:
        u = bash_ui(self._lang)
        param = Adw.PreferencesGroup(
            title=u["param_basic_title"],
            description=u["param_basic_desc"],
        )
        self._add_code_block(
            param,
            'name="John"\necho "${name}"\necho "${name/J/j}"    #=> "john" (substitution)\n'
            'echo "${name:0:2}"    #=> "Jo" (slicing)\necho "${name::2}"     #=> "Jo" (slicing)\n'
            'echo "${name::-1}"    #=> "Joh" (slicing)\necho "${name:(-1)}"   #=> "n" (from right)\n'
            'echo "${name:(-2):1}" #=> "h" (from right)\necho "${food:-Cake}"  #=> $food or "Cake"',
        )
        self._add_code_block(
            param,
            "length=2\necho \"${name:0:length}\"  #=> \"Jo\"",
        )
        self._add_text_row(param, "See: Parameter expansion")
        self._add_code_block(
            param,
            'str="/path/to/foo.cpp"\necho "${str%.cpp}"    # /path/to/foo\n'
            'echo "${str%.cpp}.o"  # /path/to/foo.o\necho "${str%/*}"      # /path/to\n\n'
            'echo "${str##*.}"     # cpp (extension)\necho "${str##*/}"     # foo.cpp (basepath)\n\n'
            'echo "${str#*/}"      # path/to/foo.cpp\necho "${str##*/}"     # foo.cpp\n\n'
            'echo "${str/foo/bar}" # /path/to/bar.cpp',
        )
        self._add_code_block(
            param,
            'str="Hello world"\necho "${str:6:5}"    # "world"\necho "${str: -5:5}"  # "world"',
        )
        self._add_code_block(
            param,
            'src="/path/to/foo.cpp"\nbase=${src##*/}   #=> "foo.cpp" (basepath)\n'
            'dir=${src%$base}  #=> "/path/to/" (dirpath)\ndir=${src%/*}     #=> "/path/to" (dirpath)',
        )
        self._append_group(col,param)

        prefix = Adw.PreferencesGroup(title=u["param_prefix_title"], description=u["param_prefix_desc"])
        self._add_code_block(
            prefix,
            'prefix_a=one\nprefix_b=two\necho ${!prefix_*}  # all variable names starting with prefix_',
        )
        self._add_text_row(prefix, "prefix_a prefix_b")
        self._append_group(col,prefix)

        indir = Adw.PreferencesGroup(title=u["indir_title"])
        self._add_code_block(
            indir,
            'name=joe\npointer=name\necho ${!pointer}\n# joe',
        )
        self._append_group(col,indir)

        subst = Adw.PreferencesGroup(title=u["subst_title"])
        self._add_table_row(subst, "${foo%suffix}", "Remove suffix")
        self._add_table_row(subst, "${foo#prefix}", "Remove prefix")
        self._add_table_row(subst, "${foo%%suffix}", "Remove long suffix")
        self._add_table_row(subst, "${foo/%suffix}", "Remove long suffix")
        self._add_table_row(subst, "${foo##prefix}", "Remove long prefix")
        self._add_table_row(subst, "${foo/#prefix}", "Remove long prefix")
        self._add_table_row(subst, "${foo/from/to}", "Replace first match")
        self._add_table_row(subst, "${foo//from/to}", "Replace all")
        self._add_table_row(subst, "${foo/%from/to}", "Replace suffix")
        self._add_table_row(subst, "${foo/#from/to}", "Replace prefix")
        self._append_group(col,subst)

        comments = Adw.PreferencesGroup(title=u["comments_title"])
        self._add_code_block(
            comments,
            "# Single line comment\n: '\nThis is a\nmulti line\ncomment\n'",
        )
        self._append_group(col,comments)

        substrings = Adw.PreferencesGroup(title=u["substrings_title"])
        self._add_table_row(substrings, "${foo:0:3}", "Substring (position, length)")
        self._add_table_row(substrings, "${foo:(-3):3}", "Substring from the right")
        self._add_table_row(substrings, "${#foo}", "Length of $foo")
        self._append_group(col,substrings)

        manip = Adw.PreferencesGroup(title=u["manip_title"])
        self._add_code_block(
            manip,
            'str="HELLO WORLD!"\necho "${str,}"   #=> "hELLO WORLD!" (lowercase 1st letter)\n'
            'echo "${str,,}"  #=> "hello world!" (all lowercase)\n\nstr="hello world!"\n'
            'echo "${str^}"   #=> "Hello world!" (uppercase 1st letter)\n'
            'echo "${str^^}"  #=> "HELLO WORLD!" (all uppercase)',
        )
        self._append_group(col,manip)

        defaults = Adw.PreferencesGroup(title=u["defaults_title"])
        self._add_table_row(defaults, "${foo:-val}", "$foo, or val if unset (or null)")
        self._add_table_row(defaults, "${foo:=val}", "Set $foo to val if unset (or null)")
        self._add_table_row(defaults, "${foo:+val}", "val if $foo is set (and not null)")
        self._add_table_row(
            defaults,
            "${foo:?message}",
            "Show error message and exit if $foo is unset (or null)",
        )
        self._add_text_row(
            defaults,
            u["defaults_footer"],
        )
        self._append_group(col,defaults)

        loops = Adw.PreferencesGroup(title=u["loops_basic_title"], description=u["loops_basic_desc"])
        self._add_code_block(
            loops,
            'for i in /etc/rc.*; do\n  echo "$i"\ndone',
        )
        g2 = Adw.PreferencesGroup(title=u["loops_clike_title"], description=u["loops_clike_desc"])
        self._add_code_block(
            g2,
            "for ((i = 0 ; i < 100 ; i++)); do\n  echo \"$i\"\ndone",
        )
        self._append_group(col,loops)
        self._append_group(col,g2)

        ranges = Adw.PreferencesGroup(title=u["loops_ranges_title"], description=u["loops_ranges_desc"])
        self._add_code_block(
            ranges,
            'for i in {1..5}; do\n    echo "Welcome $i"\ndone',
        )
        self._add_code_block(
            ranges,
            "for i in {5..50..5}; do\n    echo \"Welcome $i\"\ndone",
        )
        self._append_group(col,ranges)

        read_lines = Adw.PreferencesGroup(title=u["loops_read_title"], description=u["loops_read_desc"])
        self._add_code_block(
            read_lines,
            'while read -r line; do\n  echo "$line"\ndone <file.txt',
        )
        self._add_code_block(read_lines, "while true; do\n  ···\ndone")
        self._append_group(col,read_lines)

        fdef = Adw.PreferencesGroup(title=u["func_def_title"], description=u["func_def_desc"])
        self._add_code_block(
            fdef,
            'myfunc() {\n    echo "hello $1"\n}\n# Same as above (alternate syntax)\nfunction myfunc {\n    echo "hello $1"\n}\nmyfunc "John"',
        )
        self._append_group(col,fdef)

        fret = Adw.PreferencesGroup(title=u["func_ret_title"], description=u["func_ret_desc"])
        self._add_code_block(
            fret,
            "myfunc() {\n    local myresult='some value'\n    echo \"$myresult\"\n}\nresult=$(myfunc)",
        )
        self._append_group(col,fret)

        ferr = Adw.PreferencesGroup(title=u["func_err_title"], description=u["func_err_desc"])
        self._add_code_block(
            ferr,
            'myfunc() {\n  return 1\n}\nif myfunc; then\n  echo "success"\nelse\n  echo "failure"\nfi',
        )
        self._append_group(col,ferr)

        args = Adw.PreferencesGroup(title=u["func_args_title"], description=u["func_args_desc"])
        self._add_table_row(args, "$#", "Number of arguments")
        self._add_table_row(args, "$*", "All positional arguments (as a single word)")
        self._add_table_row(args, "$@", "All positional arguments (as separate strings)")
        self._add_table_row(args, "$1", "First argument")
        self._add_table_row(args, "$_", "Last argument of the previous command")
        self._add_text_row(
            args,
            "Note: $@ and $* must be quoted to perform as described. Otherwise they behave the same.",
        )
        self._add_text_row(args, "See: Special parameters")
        self._append_group(col, args)
        # ===== Column 3 content (now merged into Column 2) =====
        cond = Adw.PreferencesGroup(
            title=u["cond_basics_title"],
            description=u["cond_basics_desc"],
        )
        self._add_text_row(
            cond,
            "Any program with the same logic (grep, ping, …) can be used as a condition.",
        )
        self._add_table_row(cond, "[[ -z STRING ]]", "Empty string")
        self._add_table_row(cond, "[[ -n STRING ]]", "Not empty string")
        self._add_table_row(cond, "[[ STRING == STRING ]]", "Equal")
        self._add_table_row(cond, "[[ STRING != STRING ]]", "Not equal")
        self._add_table_row(cond, "[[ NUM -eq NUM ]]", "Equal")
        self._add_table_row(cond, "[[ NUM -ne NUM ]]", "Not equal")
        self._add_table_row(cond, "[[ NUM -lt NUM ]]", "Less than")
        self._add_table_row(cond, "[[ NUM -le NUM ]]", "Less than or equal")
        self._add_table_row(cond, "[[ NUM -gt NUM ]]", "Greater than")
        self._add_table_row(cond, "[[ NUM -ge NUM ]]", "Greater than or equal")
        self._add_table_row(cond, "[[ STRING =~ STRING ]]", "Regexp")
        self._add_table_row(cond, "(( NUM < NUM ))", "Numeric conditions")
        self._append_group(col,cond)

        morec = Adw.PreferencesGroup(title=u["cond_more_title"], description=u["cond_more_desc"])
        self._add_table_row(morec, "[[ -o noclobber ]]", "If OPTIONNAME is enabled")
        self._add_table_row(morec, "[[ ! EXPR ]]", "Not")
        self._add_table_row(morec, "[[ X && Y ]]", "And")
        self._add_table_row(morec, "[[ X || Y ]]", "Or")
        self._append_group(col,morec)

        files = Adw.PreferencesGroup(title=u["cond_files_title"], description=u["cond_files_desc"])
        self._add_table_row(files, "[[ -e FILE ]]", "Exists")
        self._add_table_row(files, "[[ -r FILE ]]", "Readable")
        self._add_table_row(files, "[[ -h FILE ]]", "Symlink")
        self._add_table_row(files, "[[ -d FILE ]]", "Directory")
        self._add_table_row(files, "[[ -w FILE ]]", "Writable")
        self._add_table_row(files, "[[ -s FILE ]]", "Size is > 0 bytes")
        self._add_table_row(files, "[[ -f FILE ]]", "File")
        self._add_table_row(files, "[[ -x FILE ]]", "Executable")
        self._add_table_row(files, "[[ FILE1 -nt FILE2 ]]", "1 is more recent than 2")
        self._add_table_row(files, "[[ FILE1 -ot FILE2 ]]", "2 is more recent than 1")
        self._add_table_row(files, "[[ FILE1 -ef FILE2 ]]", "Same files")
        self._append_group(col,files)

        cex = Adw.PreferencesGroup(title=u["cond_ex_title"], description=u["cond_ex_desc"])
        self._add_code_block(
            cex,
            '# String\nif [[ -z "$string" ]]; then\n  echo "String is empty"\n'
            'elif [[ -n "$string" ]]; then\n  echo "String is not empty"\nelse\n  echo "This never happens"\nfi',
        )
        self._add_code_block(cex, "# Combinations\nif [[ X && Y ]]; then\n  ...\nfi")
        self._add_code_block(cex, '# Equal\nif [[ "$A" == "$B" ]]')
        self._add_code_block(cex, '# Regex\nif [[ "A" =~ . ]]')
        self._add_code_block(
            cex,
            'if (( $a < $b )); then\n   echo "$a is smaller than $b"\nfi',
        )
        self._add_code_block(
            cex,
            'if [[ -e "file.txt" ]]; then\n  echo "file exists"\nfi',
        )
        self._append_group(col, cex)

        opts = Adw.PreferencesGroup(title=u["opts_title"], description=u["opts_desc"])
        self._add_code_block(
            opts,
            "set -o noclobber  # Avoid overlay files (echo \"hi\" > foo)\n"
            "set -o errexit    # Exit upon error\nset -o pipefail   # Unveils hidden failures\n"
            "set -o nounset    # Exposes unset variables",
        )
        self._append_group(col, opts)

        shopt = Adw.PreferencesGroup(title=u["shopt_title"], description=u["shopt_desc"])
        self._add_code_block(
            shopt,
            "shopt -s nullglob    # Non-matching globs removed  ('*.foo' => '')\n"
            "shopt -s failglob    # Non-matching globs throw errors\n"
            "shopt -s nocaseglob  # Case insensitive globs\n"
            "shopt -s dotglob     # Wildcards match dotfiles\n"
            "shopt -s globstar    # Allow ** for recursive matches",
        )
        self._add_text_row(
            shopt,
            "Set GLOBIGNORE as a colon-separated list of patterns removed from glob matches.",
        )
        self._append_group(col, shopt)

    def _add_text_row(self, group: Adw.PreferencesGroup, text: str) -> None:
        lbl = Gtk.Label(label=text, xalign=0.0, wrap=True)
        lbl.add_css_class("bash-cheatsheet-text")
        lbl.set_margin_start(16)
        lbl.set_margin_end(16)
        lbl.set_margin_top(8)
        lbl.set_margin_bottom(8)
        lbl.set_max_width_chars(60)
        group.add(lbl)

    def _add_code_block(self, group: Adw.PreferencesGroup, code: str) -> None:
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer_box.set_margin_start(16)
        outer_box.set_margin_end(16)
        outer_box.set_margin_top(10)
        outer_box.set_margin_bottom(10)
        outer_box.add_css_class("card")
        outer_box.add_css_class("bash-code-block")

        # Split code into lines for individual row styling
        lines = code.split('\n')
        
        for idx, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                continue
            
            # Row container
            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            row_box.set_margin_start(16)
            row_box.set_margin_end(12)
            row_box.set_margin_top(10)
            row_box.set_margin_bottom(10)
            
            # Code line label
            lbl = Gtk.Label(label=line, xalign=0.0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
            lbl.add_css_class("bash-code-label")
            lbl.set_hexpand(True)
            lbl.set_selectable(True)
            row_box.append(lbl)

            # Copy button for this line
            copy_btn = Gtk.Button(icon_name="edit-copy-symbolic")
            copy_btn.set_valign(Gtk.Align.CENTER)
            copy_btn.set_has_frame(False)
            copy_btn.add_css_class("flat")
            copy_btn.connect("clicked", lambda _b, l=line: _copy_cmd(l))
            row_box.append(copy_btn)

            outer_box.append(row_box)
            
            # Add separator line between rows (but not after the last one)
            if idx < len(lines) - 1 and lines[idx + 1].strip():
                separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                separator.set_margin_start(16)
                separator.set_margin_end(12)
                separator.set_margin_top(4)
                separator.set_margin_bottom(4)
                outer_box.append(separator)

        group.add(outer_box)

    def _add_table_row(self, group: Adw.PreferencesGroup, key: str, val: str) -> None:
        # Outer container with card styling
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_margin_start(16)
        container.set_margin_end(16)
        container.set_margin_top(10)
        container.set_margin_bottom(10)
        container.add_css_class("card")
        container.add_css_class("bash-table-card")
        
        # Inner row with content
        row = Adw.ActionRow()
        row.set_use_markup(False)
        row.set_title(key)
        row.set_subtitle(val)
        row.set_margin_start(16)
        row.set_margin_end(16)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        row.add_css_class("bash-table-row")
        
        # Style the title (key) with accent color
        title_widget = row.get_first_child()
        if title_widget:
            title_widget.add_css_class("bash-table-key")
        
        # Style the subtitle (value)
        if hasattr(row, 'get_child'):
            child = row.get_child()
            if child:
                child.add_css_class("bash-table-value")
        
        btn = Gtk.Button(icon_name="edit-copy-symbolic")
        btn.set_valign(Gtk.Align.CENTER)
        btn.set_has_frame(False)
        btn.add_css_class("flat")
        btn.connect("clicked", lambda _b, k=key: _copy_cmd(k))
        row.add_suffix(btn)
        container.append(row)
        group.add(container)

    def _add_link_row(self, group: Adw.PreferencesGroup, title: str, url: str) -> None:
        # Outer container with card styling
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.set_margin_start(16)
        container.set_margin_end(16)
        container.set_margin_top(10)
        container.set_margin_bottom(10)
        container.add_css_class("card")
        container.add_css_class("bash-link-card")
        
        # Inner row with content
        row = Adw.ActionRow()
        row.set_use_markup(False)
        row.set_title(title)
        row.set_subtitle(url)
        row.set_margin_start(16)
        row.set_margin_end(16)
        row.set_margin_top(12)
        row.set_margin_bottom(12)
        row.add_css_class("bash-link-row")
        
        # Style title as clickable link
        title_widget = row.get_first_child()
        if title_widget:
            title_widget.add_css_class("bash-link-title")
        
        # Style URL with monospace
        if hasattr(row, 'get_child'):
            child = row.get_child()
            if child:
                child.add_css_class("bash-link-url")
        
        container.append(row)
        group.add(container)
