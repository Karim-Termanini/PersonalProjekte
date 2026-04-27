"""HypeDevHome — Tests for the CPUWidget."""

from __future__ import annotations

from ui.widgets.cpu_widget import CPUWidget


def test_cpu_widget_instantiates() -> None:
    widget = CPUWidget()
    assert widget is not None
    assert widget.widget_id == "cpu"


def test_cpu_widget_update() -> None:
    widget = CPUWidget()
    widget._on_cpu_data(
        total_percent=45.5,
        core_percents=[10, 20, 30, 40],
        core_count=4,
        frequency_mhz=3200,
        load_avg=(1.5, 1.2, 1.0),
        temperature_c=55.0,
    )
    assert widget._total_percent == 45.5
    assert widget._core_percents == [10, 20, 30, 40]
    assert widget._frequency_mhz == 3200
    assert widget._load_avg == (1.5, 1.2, 1.0)
    assert widget._temperature_c == 55.0
