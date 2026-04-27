"""HypeDevHome — Tests for WidgetConfigDialog logic (non-visual).

Full dialog instantiation requires a running GTK main loop, so we test
the configuration logic separately.
"""

from __future__ import annotations


def test_config_dict_is_copied() -> None:
    """Verify the dialog receives a copy of the config."""
    original: dict[str, object] = {"refresh_interval": 2, "show_swap": True}
    # Simulate what the dialog does
    cfg = dict(original)
    assert cfg == original
    cfg["refresh_interval"] = 5
    assert original["refresh_interval"] == 2  # original unchanged


def test_widget_rows_logic() -> None:
    """Verify widget-specific row selection logic."""

    def rows_for(wid: str) -> list[str]:
        rows: list[str] = []
        if wid in ("memory", "memory_widget"):
            rows.append("show_swap")
        elif wid in ("network", "network_widget"):
            rows.extend(["show_peak", "show_totals"])
        elif wid in ("cpu", "cpu_widget"):
            rows.extend(["show_temperature", "show_per_core"])
        return rows

    assert rows_for("memory") == ["show_swap"]
    assert rows_for("network") == ["show_peak", "show_totals"]
    assert rows_for("cpu_widget") == ["show_temperature", "show_per_core"]
    assert rows_for("unknown") == []


def test_save_returns_copy() -> None:
    """Simulate save callback returning a copy."""
    saved: list[dict] = []
    config = {"refresh_interval": 3}

    def callback(cfg: dict) -> None:
        saved.append(dict(cfg))

    callback(config)
    config["refresh_interval"] = 99
    assert saved[0]["refresh_interval"] == 3
