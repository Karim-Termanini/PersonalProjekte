"""HypeDevHome — Tests for the enhanced event bus."""

from __future__ import annotations

import pytest

from core.events import EventBus

# ── Basic subscribe / emit ──────────────────────────────


def test_subscribe_and_emit() -> None:
    bus = EventBus()
    results: list[int] = []

    def handler(value: int) -> None:
        results.append(value)

    bus.subscribe("test.event", handler)
    bus.emit("test.event", value=42)
    assert results == [42]


def test_multiple_subscribers() -> None:
    bus = EventBus()
    results: list[str] = []

    bus.subscribe("evt", lambda msg: results.append(f"A:{msg}"))
    bus.subscribe("evt", lambda msg: results.append(f"B:{msg}"))

    bus.emit("evt", msg="hello")
    assert results == ["A:hello", "B:hello"]


def test_unsubscribe() -> None:
    bus = EventBus()
    results: list[int] = []

    def handler(n: int) -> None:
        results.append(n)

    bus.subscribe("x", handler)
    bus.emit("x", n=1)
    bus.unsubscribe("x", handler)
    bus.emit("x", n=2)
    assert results == [1]


# ── Error handling ──────────────────────────────────────


def test_handler_error_does_not_stop_others() -> None:
    bus = EventBus()
    results: list[int] = []

    def broken() -> None:
        raise RuntimeError("boom")

    bus.subscribe("e", broken)
    bus.subscribe("e", lambda: results.append(1))
    bus.emit("e")
    assert results == [1]


# ── Validation ──────────────────────────────────────────


def test_subscribe_empty_event_name_raises() -> None:
    bus = EventBus()
    with pytest.raises(ValueError, match="non-empty string"):
        bus.subscribe("", lambda: None)


# ── Debug mode ──────────────────────────────────────────


def test_debug_mode_emits_timing_logs(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus(debug=True)
    bus.subscribe("t", lambda: None)
    with caplog.at_level("DEBUG"):
        bus.emit("t")
    assert "Emitting 't'" in caplog.text
    assert "took" in caplog.text


# ── Listener count ──────────────────────────────────────


def test_listener_count() -> None:
    bus = EventBus()
    assert bus.listener_count == 0
    bus.subscribe("a", lambda: None)
    bus.subscribe("b", lambda: None)
    assert bus.listener_count == 2
    bus.clear("a")
    assert bus.listener_count == 1


def test_has_listeners() -> None:
    bus = EventBus()
    assert not bus.has_listeners("x")
    bus.subscribe("x", lambda: None)
    assert bus.has_listeners("x")


# ── Clear ───────────────────────────────────────────────


def test_clear_all() -> None:
    bus = EventBus()
    bus.subscribe("a", lambda: None)
    bus.subscribe("b", lambda: None)
    bus.clear()
    assert bus.listener_count == 0
