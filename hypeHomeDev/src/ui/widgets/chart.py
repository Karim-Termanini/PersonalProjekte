"""HypeDevHome — Simple line chart widget using Gtk.DrawingArea.

A lightweight, anti-aliased line chart suitable for real-time monitoring
data (CPU, memory, network speeds).  Features auto-scaling Y axis,
optional grid lines, and configurable colours.

Usage
-----
>>> chart = LineChart(max_points=60, line_color="#3584e4")
>>> chart.add_point(42.5)
>>> chart.add_point(55.0)
"""

from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, PangoCairo  # noqa: E402


class LineChart(Gtk.DrawingArea):
    """A real-time line chart rendered on a ``Gtk.DrawingArea``.

    Parameters
    ----------
    max_points : int
        Maximum number of data points displayed (oldest are dropped).
    line_color : str
        CSS colour string for the line (default: GNOME blue).
    fill_color : str
        Semi-transparent fill colour under the line (default: derived).
    line_width : float
        Stroke width in pixels.
    show_grid : bool
        Draw subtle horizontal grid lines.
    show_labels : bool
        Draw Y-axis min/max labels.
    """

    def __init__(
        self,
        max_points: int = 60,
        line_color: str = "#3584e4",
        fill_color: str = "",
        line_width: float = 2.0,
        show_grid: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._max_points = max_points
        self._line_color = line_color
        self._fill_color = fill_color or self._derive_fill(line_color)
        self._line_width = line_width
        self._show_grid = show_grid
        self._show_labels = show_labels
        self._data: list[float] = []

        self.set_draw_func(self._draw, None)
        self.set_size_request(-1, 80)

    # ── Public API ──────────────────────────────────────────

    @property
    def max_points(self) -> int:
        return self._max_points

    @max_points.setter
    def max_points(self, value: int) -> None:
        self._max_points = value
        while len(self._data) > self._max_points:
            self._data.pop(0)
        self.queue_draw()

    def add_point(self, value: float) -> None:
        """Append *value* to the chart, dropping oldest if full."""
        self._data.append(value)
        if len(self._data) > self._max_points:
            self._data.pop(0)
        self.queue_draw()

    def set_data(self, values: list[float]) -> None:
        """Replace all data points."""
        self._data = list(values[-self._max_points :])
        self.queue_draw()

    def clear(self) -> None:
        self._data.clear()
        self.queue_draw()

    @property
    def data(self) -> list[float]:
        return list(self._data)

    # ── Drawing ─────────────────────────────────────────────

    def _draw(
        self,
        _drawing_area: Gtk.DrawingArea,
        ctx: Any,
        width: int,
        height: int,
        _user_data: Any,
    ) -> None:
        padding_top = 10 if self._show_labels else 4
        padding_bottom = 4
        padding_left = 4
        padding_right = 36 if self._show_labels else 4

        chart_w = width - padding_left - padding_right
        chart_h = height - padding_top - padding_bottom

        if chart_w <= 0 or chart_h <= 0:
            return

        # Background
        ctx.set_source_rgba(0, 0, 0, 0)
        ctx.paint()

        if not self._data:
            return

        data_min = min(self._data)
        data_max = max(self._data)
        # Add 10% padding to Y range so extremes don't touch edges
        y_range = data_max - data_min if data_max != data_min else 10
        y_min = max(0, data_min - y_range * 0.1)
        y_max = data_max + y_range * 0.1
        y_range = y_max - y_min if y_max != y_min else 1

        n = len(self._data)

        # Grid lines
        if self._show_grid:
            self._draw_grid(
                ctx,
                width,
                height,
                padding_top,
                padding_bottom,
                padding_left,
                padding_right,
                y_min,
                y_max,
                y_range,
            )

        # Build path points
        points: list[tuple[float, float]] = []
        for i, val in enumerate(self._data):
            x = padding_left + (i / max(n - 1, 1)) * chart_w
            y = padding_top + chart_h - ((val - y_min) / y_range) * chart_h
            points.append((x, y))

        # Fill under line
        if len(points) >= 2:
            ctx.set_source_rgba(*self._parse_hex(self._fill_color))
            ctx.move_to(points[0][0], points[0][1])
            for px, py in points[1:]:
                ctx.line_to(px, py)
            ctx.line_to(points[-1][0], padding_top + chart_h)
            ctx.line_to(points[0][0], padding_top + chart_h)
            ctx.close_path()
            ctx.fill()

            # Line
            ctx.set_source_rgba(*self._parse_hex(self._line_color))
            ctx.set_line_width(self._line_width)
            ctx.set_line_cap(1)  # ROUND
            ctx.set_line_join(1)  # ROUND
            ctx.move_to(points[0][0], points[0][1])
            for px, py in points[1:]:
                ctx.line_to(px, py)
            ctx.stroke()

        # Y-axis labels
        if self._show_labels:
            self._draw_labels(
                ctx, padding_top, padding_bottom, padding_left, chart_w, y_min, y_max
            )

    def _draw_grid(
        self,
        ctx: Any,
        width: int,
        height: int,
        pad_t: int,
        pad_b: int,
        pad_l: int,
        pad_r: int,
        y_min: float,
        y_max: float,
        y_range: float,
    ) -> None:
        ctx.set_source_rgba(0.5, 0.5, 0.5, 0.15)
        ctx.set_line_width(1)
        chart_h = height - pad_t - pad_b
        # 4 horizontal grid lines
        for i in range(1, 4):
            y = pad_t + (i / 4) * chart_h
            ctx.move_to(pad_l, y)
            ctx.line_to(width - pad_r, y)
            ctx.stroke()

    def _draw_labels(
        self,
        ctx: Any,
        pad_t: int,
        pad_b: int,
        pad_l: int,
        chart_w: float,
        y_min: float,
        y_max: float,
    ) -> None:
        ctx.set_source_rgba(0.5, 0.5, 0.5, 0.7)
        layout = self.create_pango_layout(f"{y_max:.0f}")
        ctx.move_to(pad_l + chart_w + 4, pad_t - 2)
        PangoCairo.update_layout(ctx, layout)
        PangoCairo.show_layout(ctx, layout)

        layout = self.create_pango_layout(f"{y_min:.0f}")
        chart_h = self.get_allocated_height() - pad_t - pad_b
        ctx.move_to(pad_l + chart_w + 4, pad_t + chart_h - 10)
        PangoCairo.update_layout(ctx, layout)
        PangoCairo.show_layout(ctx, layout)

    # ── Helpers ─────────────────────────────────────────────

    @staticmethod
    def _derive_fill(hex_color: str) -> str:
        """Create a semi-transparent version of *hex_color*."""
        return hex_color + "33"

    @staticmethod
    def _parse_hex(hex_color: str) -> tuple[float, float, float, float]:
        """Convert ``#RRGGBB`` or ``#RRGGBBAA`` to (r, g, b, a) 0-1 floats."""
        h = hex_color.lstrip("#")
        if len(h) == 6:
            r = int(h[0:2], 16) / 255
            g = int(h[2:4], 16) / 255
            b = int(h[4:6], 16) / 255
            a = 1.0
        elif len(h) == 8:
            r = int(h[0:2], 16) / 255
            g = int(h[2:4], 16) / 255
            b = int(h[4:6], 16) / 255
            a = int(h[6:8], 16) / 255
        else:
            r = g = b = 0.5
            a = 1.0
        return r, g, b, a
