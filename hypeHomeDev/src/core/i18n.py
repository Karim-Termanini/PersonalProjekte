"""HypeDevHome — Internationalization (i18n) framework.

Uses gettext for string extraction and translation.

Supported locales (Phase 1):
    - en (English) — default
    - ar (Arabic) — placeholder
"""

from __future__ import annotations

import gettext
import locale
import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Where compiled translation files (.mo) are stored.
_LOCALE_DIR = Path(__file__).resolve().parent.parent.parent / "locale"

_domain = "hypedevhome"
_translator: gettext.NullTranslations | None = None
_current_locale: str | None = None


def setup_i18n(locale_name: str | None = None) -> None:
    """Initialise the translation system.

    Parameters
    ----------
    locale_name : str | None
        Explicit locale (e.g. ``"ar"`` or ``"en"``).  If ``None`` the
        system locale is detected automatically.
    """
    global _translator, _current_locale

    if locale_name is None:
        try:
            locale_name = locale.getdefaultlocale()[0] or "en"
        except Exception:
            locale_name = "en"

    # Normalise: "en_US" -> "en", "ar_EG" -> "ar"
    _current_locale = locale_name.split("_")[0]

    if _current_locale == "en":
        _translator = gettext.NullTranslations()
        log.info("i18n: English (no translation)")
        return

    mo_path = _LOCALE_DIR / _current_locale / "LC_MESSAGES" / f"{_domain}.mo"
    if mo_path.exists():
        with mo_path.open("rb") as f:
            _translator = gettext.GNUTranslations(f)
        log.info("i18n: loaded translations for '%s'", _current_locale)
    else:
        _translator = gettext.NullTranslations()
        log.info("i18n: no translation for '%s', falling back to English", _current_locale)


def _(text: str) -> str:
    """Translate *text* using the current locale."""
    if _translator is not None:
        return _translator.gettext(text)
    return text


def get_current_locale() -> str:
    """Return the currently active locale code."""
    return _current_locale or "en"


def is_rtl() -> bool:
    """Return ``True`` if the current locale uses right-to-left layout."""
    return get_current_locale() in ("ar", "he", "fa", "ur")


def extract_strings(output_dir: str = "po") -> None:
    """Extract translatable strings from source code.

    This is a helper for developers — runs ``xgettext`` on the source tree.
    """
    import subprocess

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    cmd = [
        "xgettext",
        "--language=Python",
        "--keyword=_",
        "--output",
        f"{output_dir}/hypedevhome.pot",
        "--package-name=hypedevhome",
        "--package-version=0.1.0",
    ]

    # Find all .py files in src/
    for py_file in (Path(__file__).resolve().parent.parent / "src").rglob("*.py"):
        cmd.append(str(py_file))

    log.info("Extracting strings: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
