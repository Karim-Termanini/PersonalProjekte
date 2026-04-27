"""Tests for data-driven Workstation catalog (install + remove)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui.widgets.workstation import install_catalog as ic


def test_workstation_catalog_json_valid() -> None:
    path = Path(__file__).resolve().parents[2] / "src/ui/widgets/workstation/data/workstation_catalog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 2
    assert "placeholders" in data
    cats = data.get("categories")
    assert isinstance(cats, list)
    ids = {str(c.get("id")) for c in cats if isinstance(c, dict)}
    assert ids >= {"dev", "editors", "terminals", "wezterm_cfg", "cleanup", "config"}


def test_catalog_path_alias() -> None:
    assert ic.install_catalog_path() == ic.workstation_catalog_path()


def test_resolve_placeholders_explicit_catalog() -> None:
    cat = {"placeholders": {"GO_VERSION": "9.9.9", "NVM_VERSION": "0.1.0"}}
    assert ic.resolve_catalog_placeholders("go{{GO_VERSION}}", cat) == "go9.9.9"
    assert ic.resolve_catalog_placeholders("nvm{{NVM_VERSION}}", cat) == "nvm0.1.0"


def test_build_row_command_distro_install(monkeypatch: pytest.MonkeyPatch) -> None:
    ic.clear_install_catalog_cache()
    monkeypatch.setattr(ic, "PACKAGE_MANAGER", "dnf")
    row = {"distro_install": "clang"}
    cmd = ic.build_row_command(row)
    assert "dnf install" in cmd
    assert "clang" in cmd


def test_build_row_command_flatpak_remove() -> None:
    row = {"flatpak_remove": "com.visualstudio.Code"}
    cmd = ic.build_row_command(row, mode="remove")
    assert "flatpak uninstall" in cmd
    assert "com.visualstudio.Code" in cmd


def test_catalog_groups_install_vs_remove() -> None:
    ic.clear_install_catalog_cache()
    entry = ic.category_from_catalog("dev")
    assert entry is not None
    gi = ic.catalog_groups(entry, "install")
    gr = ic.catalog_groups(entry, "remove")
    assert isinstance(gi, list) and isinstance(gr, list)
    assert len(gi) > 0 and len(gr) > 0

    def row_titles(groups: list) -> set[str]:
        out: set[str] = set()
        for g in groups:
            if not isinstance(g, dict):
                continue
            for r in g.get("rows", []) or []:
                if isinstance(r, dict) and r.get("title"):
                    out.add(str(r["title"]))
        return out

    ti, tr = row_titles(gi), row_titles(gr)
    assert any(t.startswith("Install") for t in ti)
    assert any(t.startswith("Uninstall") or "Remove" in t for t in tr)


def test_category_from_catalog_terminals() -> None:
    ic.clear_install_catalog_cache()
    entry = ic.category_from_catalog("terminals")
    assert entry is not None
    assert any(g.get("title") == "Alacritty" for g in entry.get("groups", []) if isinstance(g, dict))


def test_workstation_catalog_page_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk

    Gtk.init()
    from ui.widgets.workstation.panels import WorkstationCatalogPage

    page = WorkstationCatalogPage("dev")
    assert page.get_first_child() is not None


def test_workstation_catalog_page_remove_dev_builds(monkeypatch: pytest.MonkeyPatch) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk

    Gtk.init()
    from ui.widgets.workstation.panels import WorkstationCatalogPage

    page = WorkstationCatalogPage("dev", mode="remove")
    assert page.get_first_child() is not None
