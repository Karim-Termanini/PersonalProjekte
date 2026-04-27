"""HypeDevHome — Tests for the MemoryWidget."""

from __future__ import annotations

from ui.widgets.memory_widget import MemoryWidget


def test_memory_widget_instantiates() -> None:
    widget = MemoryWidget()
    assert widget is not None
    assert widget.widget_id == "memory"


def test_memory_widget_default_interval() -> None:
    widget = MemoryWidget()
    # Widget uses EventBus (sysmon.memory/sysmon.swap) so refresh_interval is 0.0
    assert widget._refresh_interval == 0.0


def test_memory_widget_update() -> None:
    widget = MemoryWidget()
    widget._on_memory_data(used=4096, total=16384, percent=25.0)
    assert widget._used == 4096
    assert widget._total == 16384
    assert widget._ram_percent == 25.0


def test_memory_widget_swap_update() -> None:
    widget = MemoryWidget()
    widget._on_swap_data(used=512, total=2048, percent=25.0)
    assert widget._swap_used == 512
    assert widget._swap_total == 2048
    assert widget._swap_percent == 25.0
