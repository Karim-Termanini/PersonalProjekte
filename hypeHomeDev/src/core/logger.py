"""HypeDevHome — Logging configuration.

Sets up rotating file logging and optional stderr output for debug mode.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.defaults import (
    DATA_DIR,
    LOG_BACKUP_COUNT,
    LOG_DATE_FORMAT,
    LOG_FILENAME,
    LOG_FORMAT,
    LOG_MAX_BYTES,
)


def setup_logging(*, debug: bool = False) -> None:
    """Configure application-wide logging.

    Parameters
    ----------
    debug:
        When ``True`` the root log level is ``DEBUG`` and a ``StreamHandler``
        writing to *stderr* is added.  Otherwise the level is ``INFO`` and
        only the rotating file handler is attached.
    """
    # Ensure data directory exists for the log file.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DATA_DIR / LOG_FILENAME

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # ── Rotating file handler ───────────────────────────
    fh = RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # ── Optional stderr handler (debug mode) ────────────
    if debug:
        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(formatter)
        root.addHandler(sh)

    logging.getLogger(__name__).debug(
        "Logging initialised (debug=%s, file=%s)",
        debug,
        log_path,
    )
