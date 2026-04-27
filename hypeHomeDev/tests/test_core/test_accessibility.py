"""HypeDevHome — Tests for accessibility utilities."""

from __future__ import annotations

from core.accessibility import is_rtl


def test_is_rtl_arabic() -> None:
    assert is_rtl("ar") is True


def test_is_rtl_hebrew() -> None:
    assert is_rtl("he") is True


def test_is_rtl_persian() -> None:
    assert is_rtl("fa") is True


def test_is_rtl_urdu() -> None:
    assert is_rtl("ur") is True


def test_is_rtl_english() -> None:
    assert is_rtl("en") is False


def test_is_rtl_french() -> None:
    assert is_rtl("fr") is False


def test_is_rtl_with_region() -> None:
    assert is_rtl("ar_EG") is True
    assert is_rtl("en_US") is False
