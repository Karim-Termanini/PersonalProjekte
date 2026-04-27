"""HypeDevHome — Tests for the error handling system."""

from __future__ import annotations

import os

import pytest

from core.errors import ToastLevel


def test_toast_level_enum() -> None:
    assert ToastLevel.INFO.value == "info"
    assert ToastLevel.SUCCESS.value == "success"
    assert ToastLevel.WARNING.value == "warning"
    assert ToastLevel.ERROR.value == "error"


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="Requires display server",
)
def test_show_toast_api_exists() -> None:
    from core.errors import show_toast

    show_toast("Test message", level=ToastLevel.INFO)


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="Requires display server",
)
def test_show_error_toast_api_exists() -> None:
    from core.errors import show_error_toast

    show_error_toast("Error occurred")
    show_error_toast("Error occurred", retry=lambda: None)


@pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="Requires display server",
)
def test_show_error_dialog_api_exists() -> None:
    from core.errors import show_error_dialog

    show_error_dialog("Title", "Message")
    show_error_dialog("Title", "Message", details="Extra info")
