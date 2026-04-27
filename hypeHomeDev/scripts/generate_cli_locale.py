#!/usr/bin/env python3
"""Build desktop_cli_locale.json (DE/AR) from parsed CLI cheatsheet strings.

Uses the public Lingva API. Run from repo root:
  PYTHONPATH=src python3 scripts/generate_cli_locale.py

Resumes from an existing JSON (merges). Uses long delays to reduce HTTP 429.
"""

from __future__ import annotations

import json
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ui.widgets.workstation.desktop_cli_reference_page import (  # noqa: E402
    _CLI_UI,
    parse_desktop_cli_md,
)

OUT = ROOT / "src/ui/widgets/workstation/desktop_cli_locale.json"
DELAY_SEC = 12.0
MAX_RETRIES = 8


def _tr(text: str, tgt: str) -> str:
    url = f"https://lingva.ml/api/v1/en/{tgt}/{urllib.parse.quote(text, safe='')}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; hypeHomeDev-locale-gen/1.0)"},
    )
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())["translation"]
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt + 1 < MAX_RETRIES:
                wait = 45 * (attempt + 1) + random.uniform(0, 8)
                print(f"  429, sleeping {wait:.0f}s …")
                time.sleep(wait)
                continue
            raise
    msg = "translation failed"
    raise RuntimeError(msg)


def _load_partial() -> dict[str, dict[str, dict[str, str]]]:
    if not OUT.is_file():
        return {"de": {"sections": {}, "subtitles": {}}, "ar": {"sections": {}, "subtitles": {}}}
    data = json.loads(OUT.read_text(encoding="utf-8"))
    for tgt in ("de", "ar"):
        data.setdefault(tgt, {})
        data[tgt].setdefault("sections", {})
        data[tgt].setdefault("subtitles", {})
    return data


def main() -> None:
    md_path = ROOT / "src/ui/widgets/workstation/desktop_cli_reference.md"
    raw = md_path.read_text(encoding="utf-8")
    u = _CLI_UI["en"]
    sections = parse_desktop_cli_md(
        raw,
        overview_title=u["overview_title"],
        overview_desc=u["overview_desc"],
        table_row_label=u["table_row"],
    )
    titles: set[str] = set()
    subs: set[str] = set()
    for t, _d, rows in sections:
        titles.add(t)
        for _cmd, sub, _clip in rows:
            if sub and not sub.startswith("http"):
                subs.add(sub)

    out = _load_partial()
    n = 0
    total = len(titles) + len(subs)

    for title in sorted(titles):
        for tgt in ("de", "ar"):
            if out[tgt]["sections"].get(title):
                continue
            n += 1
            print(f"[{n}/{total}] section {tgt}: {title[:72]!r}")
            out[tgt]["sections"][title] = _tr(title, tgt)
            OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(DELAY_SEC + random.uniform(0, 2))

    for sub in sorted(subs):
        for tgt in ("de", "ar"):
            if out[tgt]["subtitles"].get(sub):
                continue
            n += 1
            print(f"[{n}/{total}] sub {tgt}: {sub[:72]!r}")
            out[tgt]["subtitles"][sub] = _tr(sub, tgt)
            OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
            time.sleep(DELAY_SEC + random.uniform(0, 2))

    print("done ->", OUT)


if __name__ == "__main__":
    main()
