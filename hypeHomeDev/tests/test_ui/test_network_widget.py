"""HypeDevHome — Tests for the NetworkWidget."""

from __future__ import annotations

from ui.widgets.network_widget import NetworkWidget


def _minimal_net_payload(**extra: object) -> dict:
    base = {
        "dl_speed": 0.0,
        "ul_speed": 0.0,
        "dl_bytes": 0,
        "ul_bytes": 0,
        "local_ip": "",
        "public_ip": "",
        "connected": True,
        "interfaces": [],
        "per_nic": {},
    }
    base.update(extra)
    return base


def test_network_widget_instantiates() -> None:
    widget = NetworkWidget()
    assert widget is not None
    assert widget.widget_id == "network"


def test_network_widget_default_interval() -> None:
    widget = NetworkWidget()
    assert widget._refresh_interval == 0.0


def test_network_widget_update() -> None:
    widget = NetworkWidget()
    widget._on_network_data(
        **_minimal_net_payload(
            dl_speed=1_048_576.0,
            ul_speed=524_288.0,
            local_ip="192.168.1.10",
        )
    )
    assert widget._dl_speed == 1_048_576.0
    assert widget._ul_speed == 524_288.0
    assert widget._local_ip == "192.168.1.10"
    assert widget._connected is True


def test_network_widget_peak_tracking() -> None:
    widget = NetworkWidget()
    widget._on_network_data(**_minimal_net_payload(dl_speed=1000.0, ul_speed=500.0))
    assert widget._peak_dl == 1000.0
    assert widget._peak_ul == 500.0
    widget._on_network_data(**_minimal_net_payload(dl_speed=2000.0, ul_speed=300.0))
    assert widget._peak_dl == 2000.0
    assert widget._peak_ul == 500.0


def test_network_widget_totals_from_payload() -> None:
    widget = NetworkWidget()
    widget._on_network_data(
        **_minimal_net_payload(dl_bytes=1000, ul_bytes=500, dl_speed=1.0, ul_speed=1.0)
    )
    br, bs = widget._extract_display_totals(widget._last_event)
    assert br == 1000.0
    assert bs == 500.0


def test_network_widget_per_nic_selection() -> None:
    widget = NetworkWidget()
    widget._selected_iface = "eth0"
    payload = _minimal_net_payload(
        dl_speed=999.0,
        ul_speed=888.0,
        per_nic={
            "eth0": {
                "dl_speed": 100.0,
                "ul_speed": 50.0,
                "bytes_recv": 2048,
                "bytes_sent": 1024,
                "ipv4": "10.0.0.5",
                "isup": True,
            }
        },
        interfaces=[{"name": "eth0", "ip": "10.0.0.5", "isup": True}],
    )
    widget._on_network_data(**payload)
    dl, ul, lip = widget._extract_display_speeds(widget._last_event)
    assert dl == 100.0
    assert ul == 50.0
    assert lip == "10.0.0.5"


def test_get_config_persists_interface() -> None:
    widget = NetworkWidget(network_interface="wlan0")
    cfg = widget.get_config()
    assert cfg.get("network_interface") == "wlan0"
