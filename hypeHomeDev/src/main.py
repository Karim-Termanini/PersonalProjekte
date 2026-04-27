"""HypeDevHome — Entry point with CLI argument handling."""

from __future__ import annotations

import argparse
import os
import sys

# Add the 'src' directory to sys.path to support the "src layout" structure
# when running directly from the project root.
src_dir = os.path.dirname(os.path.abspath(__file__))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)


def _install_gtk_theme_parser_log_filter() -> None:
    """Drop GTK \"Theme parser\" stderr noise from Libadwaita / system theme CSS.

    GTK 4 emits these through the default **log writer** (structured fields), not only
    ``log_set_handler``. The ``MESSAGE`` field is often exposed as a raw pointer (``int``)
    in PyGObject, so we decode it with ``ctypes.string_at``.

    The broken ``shade`` / ``mix`` / ``-gtk-icon-effect`` rules live in the system GTK
    theme or Adwaita assets — not in this app's ``src/ui/style/gtk.css``.
    """
    import ctypes

    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib

    def _utf8_from_log_field_value(val: object) -> str:
        if val is None:
            return ""
        if isinstance(val, str):
            return val
        if isinstance(val, bytes):
            return val.decode("utf-8", errors="replace")
        if isinstance(val, memoryview):
            return val.tobytes().decode("utf-8", errors="replace")
        if isinstance(val, int):
            if val == 0:
                return ""
            # PyGObject: C char* for MESSAGE may appear as an integer address.
            return ctypes.string_at(val).decode("utf-8", errors="replace")
        return ""

    def _message_from_writer_fields(fields: object, n_fields: int) -> str:
        if not fields:
            return ""
        for i in range(int(n_fields)):
            f = fields[i]
            key = f.key
            if isinstance(key, bytes):
                key = key.decode("ascii", errors="replace")
            if key != "MESSAGE":
                continue
            return _utf8_from_log_field_value(f.value)
        return ""

    def _writer(
        log_level: int,
        fields: object,
        n_fields: int,
        user_data: object,
    ) -> int:
        msg = _message_from_writer_fields(fields, n_fields)
        if msg and "Theme parser" in msg:
            return GLib.LogWriterOutput.HANDLED
        return GLib.log_writer_default(log_level, fields, user_data)

    GLib.log_set_writer_func(_writer, None)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="hypedevhome",
        description="HypeDevHome — Developer dashboard for Linux",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable debug logging (also logs to stderr)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Application entry point."""
    args = _parse_args(argv)

    # Initialise logging as early as possible.
    from core.logger import setup_logging

    setup_logging(debug=args.debug)

    import logging

    log = logging.getLogger(__name__)
    log.info("Starting HypeDevHome …")

    # Before Gtk loads: hide harmless Libadwaita theme CSS parser warnings on stderr.
    if not args.debug:
        _install_gtk_theme_parser_log_filter()

    # Initialise configuration.
    from config.manager import ConfigManager

    config = ConfigManager()
    config.load()
    log.info("Configuration loaded from %s", config.path)

    # Keep a reference in the global application state.
    from core.state import AppState

    state = AppState.get()
    state.config = config

    # Launch the GTK application.
    from app import HypeDevHomeApp

    app = HypeDevHomeApp()
    exit_code: int = app.run(sys.argv[:1])  # GTK expects sys.argv[0] only
    log.info("HypeDevHome exited with code %d", exit_code)
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
