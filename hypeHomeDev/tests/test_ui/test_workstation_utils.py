"""Tests for shared workstation command helpers."""

from __future__ import annotations

import pytest

import ui.widgets.workstation.workstation_utils as wu


def test_distro_cmd_dnf(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wu, "PACKAGE_MANAGER", "dnf")
    assert "dnf install -y" in wu._distro_cmd("foo")


def test_distro_remove_apt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wu, "PACKAGE_MANAGER", "apt")
    assert "apt remove" in wu._distro_remove("bar")


def test_distro_cmd_unknown_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wu, "PACKAGE_MANAGER", "unknown")
    assert "Install" in wu._distro_cmd("pkg")


def test_resolve_placeholders() -> None:
    catalog = {"placeholders": {"VER": "1.0.0"}}
    text = "install-{{VER}}"
    assert wu.resolve_catalog_placeholders(text, catalog) == "install-1.0.0"
    # Built-in Go placeholder (no catalog passed)
    assert "1.24.1" in wu.resolve_catalog_placeholders("go-{{GO_VERSION}}")


def test_patch_config_command() -> None:
    cmd = wu._patch_config_file("~/.test.conf", "myid", "data=1")
    assert "sed -i" in cmd
    assert "# HypeHome: [myid] START" in cmd
    assert "data=1" in cmd
