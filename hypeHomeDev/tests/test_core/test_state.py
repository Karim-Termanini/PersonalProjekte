"""HypeDevHome — Tests for the enhanced AppState."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from core.events import EventBus
from core.state import AppLifecycle, AppState


@pytest.fixture(autouse=True)
def _reset_singleton() -> Generator[None, None, None]:
    """Ensure each test gets a fresh singleton."""
    AppState.reset()
    yield
    AppState.reset()


def test_singleton() -> None:
    a = AppState.get()
    b = AppState.get()
    assert a is b


def test_default_page() -> None:
    assert AppState.get().current_page == "welcome"


def test_navigate_to_emits_event() -> None:
    state = AppState.get()
    state.event_bus = EventBus()
    pages: list[str] = []
    if state.event_bus:
        state.event_bus.subscribe("nav.page-changed", lambda new, **_: pages.append(new))

    state.navigate_to("machine_setup")
    assert pages == ["machine_setup"]
    assert state.current_page == "machine_setup"


def test_navigate_to_same_page_no_event() -> None:
    state = AppState.get()
    state.event_bus = EventBus()
    count = [0]
    if state.event_bus:
        state.event_bus.subscribe(
            "nav.page-changed", lambda **_: count.__setitem__(0, count[0] + 1)
        )

    state.navigate_to("welcome")  # same as default
    assert count[0] == 0


def test_lifecycle_states() -> None:
    state = AppState.get()
    assert state.lifecycle == AppLifecycle.INITIALIZING
    state.set_lifecycle(AppLifecycle.READY)
    assert state.lifecycle == AppLifecycle.READY
    state.set_lifecycle(AppLifecycle.RUNNING)
    assert state.lifecycle == AppLifecycle.RUNNING


def test_error_tracking() -> None:
    state = AppState.get()
    assert state.last_error is None
    assert state.error_count == 0

    err = ValueError("oops")
    state.record_error(err)
    assert state.last_error is err
    assert state.error_count == 1

    state.record_error(RuntimeError("again"))
    assert state.error_count == 2

    state.reset_errors()
    assert state.last_error is None
    assert state.error_count == 0


def test_preferences_cache() -> None:
    state = AppState.get()
    state.set_preference("theme", "dark")
    assert state.get_preference("theme") == "dark"
    assert state.get_preference("missing", 99) == 99
