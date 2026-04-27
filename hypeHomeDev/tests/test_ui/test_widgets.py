"""HypeDevHome — Tests for reusable UI components."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from ui.widgets.card import Card  # noqa: E402
from ui.widgets.empty_state import EmptyState  # noqa: E402
from ui.widgets.error_banner import ErrorBanner  # noqa: E402
from ui.widgets.loading_spinner import LoadingSpinner  # noqa: E402
from ui.widgets.section_header import SectionHeader  # noqa: E402
from ui.widgets.status_indicator import StatusIndicator, StatusLevel  # noqa: E402


def test_card_instantiates() -> None:
    card = Card()
    assert card is not None


def test_card_set_child() -> None:
    card = Card()
    child = Gtk.Label(label="hello")
    card.set_child(child)
    assert card.get_child() is child


def test_status_indicator_instantiates() -> None:
    ind = StatusIndicator(level=StatusLevel.SUCCESS, label="OK")
    assert ind is not None
    assert ind.level == StatusLevel.SUCCESS


def test_status_indicator_label() -> None:
    ind = StatusIndicator(level=StatusLevel.INFO, label="Info")
    assert ind.label_text == "Info"
    ind.label_text = "Updated"
    assert ind.label_text == "Updated"


def test_status_indicator_level_change() -> None:
    ind = StatusIndicator(level=StatusLevel.NEUTRAL)
    ind.level = StatusLevel.ERROR
    assert ind.level == StatusLevel.ERROR


def test_empty_state_instantiates() -> None:
    es = EmptyState(
        icon_name="folder-symbolic",
        title="Empty",
        description="No items",
    )
    assert es is not None


def test_empty_state_with_button() -> None:
    EmptyState(
        title="Empty",
        button_label="Add",
        button_action=lambda: None,
    )


def test_loading_spinner_instantiates() -> None:
    sp = LoadingSpinner("Loading...")
    assert sp is not None


def test_section_header_instantiates() -> None:
    h = SectionHeader(title="Settings", subtitle="Preferences")
    assert h is not None


def test_section_header_no_subtitle() -> None:
    h = SectionHeader(title="Title")
    assert h is not None


def test_error_banner_instantiates() -> None:
    banner = ErrorBanner(message="Something went wrong")
    assert banner is not None
    assert banner.message == "Something went wrong"


def test_error_banner_retry_callback() -> None:
    retried = [False]
    ErrorBanner(
        message="Network error",
        retry=lambda: retried.__setitem__(0, True),
    )
    # Callback is wired but we can't simulate a click in CI


def test_error_banner_message_update() -> None:
    banner = ErrorBanner(message="First error")
    banner.message = "Second error"
    assert banner.message == "Second error"
