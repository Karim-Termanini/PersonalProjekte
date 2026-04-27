"""HypeDevHome — Tests for the GPUWidget."""

from __future__ import annotations

from ui.widgets.gpu_widget import GPUWidget


def test_gpu_widget_instantiates() -> None:
    widget = GPUWidget()
    assert widget is not None
    assert widget.widget_id == "gpu"
    assert widget._refresh_interval == 0.0


def test_gpu_widget_event_subscription() -> None:
    """Test that GPU widget properly subscribes to EventBus."""
    widget = GPUWidget()

    # Widget should have proper initial state
    assert widget._vendor == "Unknown"
    assert widget._model == "Unknown"
    assert widget._utilization == 0.0
    assert widget._detected is False

    # Test data update via EventBus
    widget._on_gpu_data(
        vendor="NVIDIA",
        model="GeForce RTX 3080",
        utilization=75.0,
        vram_used=4096.0,
        vram_total=10240.0,
        temperature_c=68.0,
        fan_speed=50.0,
        detected=True,
    )

    assert widget._vendor == "NVIDIA"
    assert widget._model == "GeForce RTX 3080"
    assert widget._utilization == 75.0
    assert widget._temperature == 68.0
    assert widget._fan_speed == 50.0
    assert widget._detected is True


def test_gpu_widget_multi_gpu_list() -> None:
    widget = GPUWidget(gpu_index=0)
    widget._on_gpu_data(
        gpus=[
            {
                "vendor": "NVIDIA",
                "model": "GPU A",
                "utilization": 10.0,
                "vram_used": 100.0,
                "vram_total": 1000.0,
                "temperature_c": 40.0,
                "fan_speed": 30.0,
                "detected": True,
            },
            {
                "vendor": "NVIDIA",
                "model": "GPU B",
                "utilization": 20.0,
                "vram_used": 200.0,
                "vram_total": 2000.0,
                "temperature_c": 41.0,
                "fan_speed": 31.0,
                "detected": True,
            },
        ],
        gpu_count=2,
        vendor="NVIDIA",
        model="GPU A",
        utilization=10.0,
        vram_used=100.0,
        vram_total=1000.0,
        temperature_c=40.0,
        fan_speed=30.0,
        detected=True,
    )
    assert len(widget._gpus_list) == 2
    assert widget._gpu_index == 0
    assert widget._model == "GPU A"
    widget._gpu_index = 1
    widget._apply_gpu_snapshot(widget._gpus_list[1])
    assert widget._model == "GPU B"
    assert widget._utilization == 20.0


def test_gpu_get_config_persists_index() -> None:
    w = GPUWidget(gpu_index=1)
    assert w.get_config().get("gpu_index") == 1
