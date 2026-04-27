"""Load Workstation toolchain definitions from workstation_catalog.json (install + remove)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Literal

from ui.widgets.workstation.workstation_utils import (
    PACKAGE_MANAGER,
    _distro_cmd,
    _distro_remove,
)
from ui.widgets.workstation.workstation_utils import (
    resolve_catalog_placeholders as _generic_resolve_placeholders,
)

log = logging.getLogger(__name__)

_CatalogMode = Literal["install", "remove"]

_CATALOG_CACHE: dict[str, Any] | None = None


def workstation_catalog_path() -> Path:
    return Path(__file__).with_name("data") / "workstation_catalog.json"


def install_catalog_path() -> Path:
    """Backward-compatible alias for :func:`workstation_catalog_path`."""
    return workstation_catalog_path()


def load_workstation_catalog() -> dict[str, Any]:
    global _CATALOG_CACHE
    if _CATALOG_CACHE is not None:
        return _CATALOG_CACHE
    path = workstation_catalog_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        _CATALOG_CACHE = raw if isinstance(raw, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        log.exception("Failed to load workstation catalog: %s", path)
        _CATALOG_CACHE = {}
    return _CATALOG_CACHE


def load_install_catalog() -> dict[str, Any]:
    """Alias of :func:`load_workstation_catalog` (same JSON file)."""
    return load_workstation_catalog()


def clear_install_catalog_cache() -> None:
    """Test hook: force reload on next catalog load."""
    global _CATALOG_CACHE
    _CATALOG_CACHE = None


def resolve_catalog_placeholders(text: str, catalog: dict[str, Any] | None = None) -> str:
    """Replace ``{{NAME}}`` tokens using the catalog ``placeholders`` map."""
    cat = catalog or load_workstation_catalog()
    return _generic_resolve_placeholders(text, cat)


def _flatpak_remove_cmd(app_id: str) -> str:
    return f"flatpak uninstall --user -y {app_id}"


def _build_command_for_row(row: dict[str, Any], pkg_mgr: str, *, mode: _CatalogMode) -> str:
    if not isinstance(row, dict):
        return "# invalid row"

    if mode == "remove":
        if "command" in row:
            return resolve_catalog_placeholders(str(row.get("command", "")))
        if row.get("flatpak_remove"):
            return _flatpak_remove_cmd(str(row["flatpak_remove"]))
        if row.get("distro_remove") is not None:
            return _distro_remove(str(row["distro_remove"]))
        mp = row.get("distro_remove_packages")
        if isinstance(mp, dict):
            pkg = str(mp.get(pkg_mgr) or mp.get("unknown") or "")
            if not pkg:
                return f"# No removal package list for {pkg_mgr} in workstation_catalog.json"
            return _distro_remove(pkg)
        return "# incomplete removal row in workstation_catalog.json"

    if "command" in row:
        return resolve_catalog_placeholders(str(row.get("command", "")))
    if row.get("flatpak"):
        return _distro_cmd("", flatpak_id=str(row["flatpak"]))
    if row.get("distro_install") is not None:
        return _distro_cmd(str(row["distro_install"]))
    mp = row.get("distro_packages")
    if isinstance(mp, dict):
        pkg = str(mp.get(pkg_mgr) or mp.get("unknown") or "")
        if not pkg:
            return f"# No package list for {pkg_mgr} in workstation_catalog.json"
        return _distro_cmd(pkg)
    return "# incomplete row in workstation_catalog.json"


def catalog_groups(entry: dict[str, Any], mode: _CatalogMode) -> list[Any]:
    """Pick install ``groups`` vs ``removal_groups`` (fallback to ``groups`` for cleanup-only)."""
    if mode == "remove":
        rg = entry.get("removal_groups")
        if isinstance(rg, list) and rg:
            return rg
        g = entry.get("groups")
        return g if isinstance(g, list) else []
    g = entry.get("groups")
    return g if isinstance(g, list) else []


def category_from_catalog(category_id: str) -> dict[str, Any] | None:
    cat = load_workstation_catalog()
    categories = cat.get("categories")
    if not isinstance(categories, list):
        return None
    for entry in categories:
        if isinstance(entry, dict) and str(entry.get("id", "")) == category_id:
            return entry
    return None


def build_row_command(
    row: dict[str, Any],
    pkg_mgr: str | None = None,
    *,
    mode: _CatalogMode = "install",
) -> str:
    pm = pkg_mgr or PACKAGE_MANAGER
    return _build_command_for_row(row, pm, mode=mode)
