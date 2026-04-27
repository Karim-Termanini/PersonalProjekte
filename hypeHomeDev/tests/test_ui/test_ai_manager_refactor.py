"""Sanity checks for AI manager catalog + dependency JSON."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ui.widgets.workstation import ai_manager as am


def test_services_json_contains_ollama() -> None:
    path = Path(__file__).resolve().parents[2] / "src/ui/widgets/workstation/data/services.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = {str(e.get("id")) for e in data.get("services", []) if isinstance(e, dict)}
    assert "ollama" in ids


def test_ai_dependencies_schema() -> None:
    path = Path(__file__).resolve().parents[2] / "src/ui/widgets/workstation/data/ai_dependencies.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data.get("schema_version") == 1
    stacks = data.get("stacks")
    assert isinstance(stacks, dict)
    assert "nvidia_driver" in stacks
    for pm in ("dnf", "apt", "pacman", "zypper", "apk", "unknown"):
        assert pm in stacks["nvidia_driver"]


def test_ai_stack_command_resolves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(am, "_ai_deps_cache", None)
    monkeypatch.setattr(am, "PACKAGE_MANAGER", "dnf")
    cmd = am._ai_stack_command("nvidia_driver")
    assert "dnf" in cmd.lower() or "nvidia" in cmd.lower()


def test_load_service_catalog_includes_ollama() -> None:
    from ui.widgets.workstation.service_manager import _load_service_catalog

    ids = {str(s.get("id", "")) for s in _load_service_catalog()}
    assert "ollama" in ids
