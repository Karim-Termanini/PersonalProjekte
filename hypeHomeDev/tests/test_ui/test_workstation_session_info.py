"""Tests for Workstation session / desktop detection (Phase 7 Learn)."""

from __future__ import annotations

from ui.widgets.workstation.session_info import (
    desktop_session_lines,
    neovim_user_config_hint,
    session_is_hyprland,
)


def test_session_is_hyprland_from_signature():
    assert session_is_hyprland({"HYPRLAND_INSTANCE_SIGNATURE": "abc"}) is True


def test_session_is_hyprland_from_desktop():
    assert session_is_hyprland({"XDG_CURRENT_DESKTOP": "Hyprland"}) is True
    assert session_is_hyprland({"XDG_SESSION_DESKTOP": "hyprland"}) is True


def test_session_is_hyprland_negative():
    assert session_is_hyprland({"XDG_CURRENT_DESKTOP": "GNOME"}) is False
    assert session_is_hyprland({}) is False


def test_desktop_session_lines_contains_keys():
    text = desktop_session_lines({"XDG_CURRENT_DESKTOP": "GNOME", "DISPLAY": ":0"})
    assert "XDG_CURRENT_DESKTOP=GNOME" in text
    assert "DISPLAY=:0" in text
    assert "WAYLAND_DISPLAY" in text


def test_neovim_user_config_hint_is_string():
    hint = neovim_user_config_hint()
    assert isinstance(hint, str)
    assert len(hint) > 10
