"""HypeDevHome — Tests for the LineChart widget."""

from __future__ import annotations

from ui.widgets.chart import LineChart


def test_chart_instantiates() -> None:
    chart = LineChart()
    assert chart is not None
    assert chart.max_points == 60


def test_chart_custom_max_points() -> None:
    chart = LineChart(max_points=30)
    assert chart.max_points == 30


def test_add_point() -> None:
    chart = LineChart(max_points=5)
    chart.add_point(10)
    chart.add_point(20)
    chart.add_point(30)
    assert chart.data == [10, 20, 30]


def test_add_point_drops_oldest() -> None:
    chart = LineChart(max_points=3)
    chart.add_point(1)
    chart.add_point(2)
    chart.add_point(3)
    chart.add_point(4)
    assert chart.data == [2, 3, 4]


def test_set_data() -> None:
    chart = LineChart(max_points=10)
    chart.set_data([10, 20, 30])
    assert chart.data == [10, 20, 30]


def test_set_data_truncates_to_max() -> None:
    chart = LineChart(max_points=3)
    chart.set_data([1, 2, 3, 4, 5])
    assert chart.data == [3, 4, 5]


def test_clear() -> None:
    chart = LineChart()
    chart.add_point(42)
    chart.clear()
    assert chart.data == []


def test_parse_hex_6() -> None:
    r, g, b, a = LineChart._parse_hex("#3584e4")
    assert abs(r - 53 / 255) < 0.001
    assert abs(g - 132 / 255) < 0.001
    assert abs(b - 228 / 255) < 0.001
    assert a == 1.0


def test_parse_hex_8() -> None:
    r, _g, _b, a = LineChart._parse_hex("#3584e480")
    assert abs(r - 53 / 255) < 0.001
    assert abs(a - 128 / 255) < 0.001


def test_parse_hex_invalid() -> None:
    r, g, b, a = LineChart._parse_hex("#xyz")
    assert r == 0.5
    assert g == 0.5
    assert b == 0.5
    assert a == 1.0


def test_derive_fill() -> None:
    result = LineChart._derive_fill("#3584e4")
    assert result == "#3584e433"


def test_max_points_setter_truncates() -> None:
    chart = LineChart(max_points=10)
    chart.set_data(list(range(10)))
    assert len(chart.data) == 10
    chart.max_points = 3
    assert len(chart.data) == 3
