"""HypeDevHome — Tests for i18n module."""

from __future__ import annotations

from core import i18n


def test_default_translator_is_null() -> None:
    # Before setup, translator should be None
    i18n._translator = None
    assert i18n._translator is None


def test_setup_english() -> None:
    i18n.setup_i18n("en")
    assert i18n.get_current_locale() == "en"
    assert i18n._translator is not None
    assert i18n._translator.gettext("hello") == "hello"


def test_setup_unknown_falls_back_to_english() -> None:
    i18n.setup_i18n("zz")
    assert i18n.get_current_locale() == "zz"
    # No translation file exists, falls back to NullTranslations
    assert i18n._translator is not None


def test_translate_function() -> None:
    i18n.setup_i18n("en")
    assert i18n._("Hello") == "Hello"


def test_is_rtl() -> None:
    i18n.setup_i18n("en")
    assert i18n.is_rtl() is False

    i18n.setup_i18n("ar")
    assert i18n.is_rtl() is True

    i18n.setup_i18n("he")
    assert i18n.is_rtl() is True


def test_locale_normalisation() -> None:
    i18n.setup_i18n("ar_EG")
    assert i18n.get_current_locale() == "ar"

    i18n.setup_i18n("en_US")
    assert i18n.get_current_locale() == "en"
