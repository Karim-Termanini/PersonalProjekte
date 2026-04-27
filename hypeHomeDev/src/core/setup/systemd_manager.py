"""Systemd D-Bus manager helper.

Centralize systemd queries/actions via D-Bus (no shell ``systemctl``).
Supports both the **system** and **session** bus so user units (e.g. user
``ollama.service``) are visible and controllable from the same API as system
units.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import gi

gi.require_version("Gio", "2.0")

from gi.repository import Gio, GLib  # noqa: E402


_SYSTEMD_BUS_NAME = "org.freedesktop.systemd1"
_SYSTEMD_MANAGER_PATH = "/org/freedesktop/systemd1"
_SYSTEMD_MANAGER_IFACE = "org.freedesktop.systemd1.Manager"
_DBUS_PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"
_SYSTEMD_UNIT_IFACE = "org.freedesktop.systemd1.Unit"


@dataclass(frozen=True)
class SystemdUnitState:
    unit: str
    load_state: str
    active_state: str
    sub_state: str


class SystemdManager:
    """Wrapper around ``org.freedesktop.systemd1`` via ``Gio.DBusProxy``."""

    def __init__(self) -> None:
        self._managers: dict[int, Gio.DBusProxy | None] = {}
        # Last bus on which ``get_unit_state`` successfully read this unit (best-effort for start/stop).
        self._preferred_bus: dict[str, Gio.BusType] = {}

    def _manager(self, bus: Gio.BusType) -> Gio.DBusProxy | None:
        key = int(bus)
        if key in self._managers:
            return self._managers[key]
        try:
            proxy = Gio.DBusProxy.new_for_bus_sync(
                bus,
                Gio.DBusProxyFlags.NONE,
                None,
                _SYSTEMD_BUS_NAME,
                _SYSTEMD_MANAGER_PATH,
                _SYSTEMD_MANAGER_IFACE,
                None,
            )
        except GLib.Error:
            self._managers[key] = None
            return None
        self._managers[key] = proxy
        return proxy

    def is_available(self) -> bool:
        return self._manager(Gio.BusType.SYSTEM) is not None

    def get_unit_state(self, unit_name: str) -> SystemdUnitState | None:
        """Return unit state or None if the unit is unknown on both buses."""
        for bus in (Gio.BusType.SYSTEM, Gio.BusType.SESSION):
            mgr = self._manager(bus)
            if mgr is None:
                continue
            unit_path = self._get_unit_path(unit_name, mgr)
            if not unit_path:
                continue
            try:
                unit_proxy = Gio.DBusProxy.new_for_bus_sync(
                    bus,
                    Gio.DBusProxyFlags.NONE,
                    None,
                    _SYSTEMD_BUS_NAME,
                    unit_path,
                    _DBUS_PROPERTIES_IFACE,
                    None,
                )
            except GLib.Error:
                continue
            state = self._get_all_properties(unit_proxy, _SYSTEMD_UNIT_IFACE)
            if state is None:
                continue
            self._preferred_bus[unit_name] = bus
            return SystemdUnitState(
                unit=unit_name,
                load_state=str(state.get("LoadState", "")),
                active_state=str(state.get("ActiveState", "")),
                sub_state=str(state.get("SubState", "")),
            )
        return None

    def start_unit(self, unit_name: str, mode: str = "replace") -> bool:
        return self._start_stop_restart("StartUnit", unit_name, mode)

    def stop_unit(self, unit_name: str, mode: str = "replace") -> bool:
        return self._start_stop_restart("StopUnit", unit_name, mode)

    def restart_unit(self, unit_name: str, mode: str = "replace") -> bool:
        return self._start_stop_restart("RestartUnit", unit_name, mode)

    def enable_unit(self, unit_name: str, *, runtime: bool = False, force: bool = True) -> bool:
        bus = self._preferred_bus.get(unit_name, Gio.BusType.SYSTEM)
        return self._call_manager_bool(
            "EnableUnitFiles",
            GLib.Variant("(asbb)", ([unit_name], runtime, force)),
            bus,
        )

    def disable_unit(self, unit_name: str, *, runtime: bool = False) -> bool:
        bus = self._preferred_bus.get(unit_name, Gio.BusType.SYSTEM)
        return self._call_manager_bool(
            "DisableUnitFiles",
            GLib.Variant("(asb)", ([unit_name], runtime)),
            bus,
        )

    def _start_stop_restart(self, method: str, unit_name: str, mode: str) -> bool:
        buses: list[Gio.BusType] = []
        pref = self._preferred_bus.get(unit_name)
        if pref is not None:
            buses.append(pref)
        for b in (Gio.BusType.SYSTEM, Gio.BusType.SESSION):
            if b not in buses:
                buses.append(b)
        for bus in buses:
            mgr = self._manager(bus)
            if mgr is None:
                continue
            if not self._get_unit_path(unit_name, mgr):
                continue
            ok = self._call_manager_bool(
                method,
                GLib.Variant("(ss)", (unit_name, mode)),
                bus,
            )
            if ok:
                self._preferred_bus[unit_name] = bus
                return True
        return False

    def _get_unit_path(self, unit_name: str, manager: Gio.DBusProxy) -> str | None:
        try:
            result = manager.call_sync(
                "GetUnit",
                GLib.Variant("(s)", (unit_name,)),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
            if result is None:
                return None
            path = result.unpack()[0]
            return str(path)
        except GLib.Error:
            return None

    @staticmethod
    def _get_all_properties(proxy: Gio.DBusProxy, iface: str) -> dict[str, Any] | None:
        try:
            result = proxy.call_sync(
                "GetAll",
                GLib.Variant("(s)", (iface,)),
                Gio.DBusCallFlags.NONE,
                5000,
                None,
            )
            if result is None:
                return None
            data = result.unpack()[0]
            out: dict[str, Any] = {}
            for key, value in data.items():
                out[str(key)] = value.unpack() if hasattr(value, "unpack") else value
            return out
        except GLib.Error:
            return None

    def _call_manager_bool(self, method: str, params: GLib.Variant, bus: Gio.BusType) -> bool:
        mgr = self._manager(bus)
        if mgr is None:
            return False
        try:
            result = mgr.call_sync(
                method,
                params,
                Gio.DBusCallFlags.NONE,
                10000,
                None,
            )
            return result is not None
        except GLib.Error:
            return False
