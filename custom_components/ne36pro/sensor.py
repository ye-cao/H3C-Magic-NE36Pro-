"""Sensor platform for the H3C Magic NE36Pro integration."""
from __future__ import annotations

from typing import Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Ne36ProDataUpdateCoordinator, build_device_info, radio_field

_S = Callable[[dict], object]


def _g(path: list):
    def getter(data: dict):
        node = data
        for p in path:
            if not isinstance(node, dict):
                return None
            node = node.get(p)
        return node
    return getter


def _ssid(radio: str, field: str) -> _S:
    def getter(data: dict):
        return radio_field(data, radio, field)
    return getter


def _fmt_uptime(seconds) -> str | None:
    """Format uptime seconds as a human-readable zh string."""
    try:
        seconds = int(float(seconds))
    except (TypeError, ValueError):
        return None
    if seconds < 0:
        return None
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    if d:
        return f"{d}天{h}小时{m}分{s}秒"
    if h:
        return f"{h}小时{m}分{s}秒"
    if m:
        return f"{m}分{s}秒"
    return f"{s}秒"


SENSORS: list[dict] = [
    {"key": "firmware", "name": "固件版本", "getter": _g(["esps", "fwinfo", "fwVersion"]), "icon": "mdi:chip"},
    {"key": "cpu", "name": "CPU 使用率", "getter": _g(["esps", "cpu", "cpurate"]), "unit": "%", "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:cpu-64-bit"},
    {"key": "mem", "name": "内存使用率", "getter": _g(["esps", "mem", "ramrate"]), "unit": "%", "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:memory"},
    {"key": "uptime", "name": "运行时间", "getter": _g(["esps", "rt", "onlineTime"]), "kind": "uptime", "icon": "mdi:timer-outline"},
    {"key": "online", "name": "在线设备数", "getter": _g(["esps", "stanum", "countOnline"]), "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:devices"},
    {"key": "clients_2g", "name": "2.4G 设备数", "getter": _g(["esps", "stanum", "count2p4g"]), "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:wifi"},
    {"key": "clients_5g", "name": "5G 设备数", "getter": _g(["esps", "stanum", "count5g"]), "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:wifi"},
    {"key": "clients_wired", "name": "有线设备数", "getter": _g(["esps", "stanum", "countWired"]), "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:ethernet"},
    {"key": "ssid_2g", "name": "WiFi 2.4G SSID", "getter": _ssid("2.4G", "ssid"), "icon": "mdi:wifi"},
    {"key": "ssid_5g", "name": "WiFi 5G SSID", "getter": _ssid("5G", "ssid"), "icon": "mdi:wifi"},
    {"key": "ntp_type", "name": "NTP 模式", "getter": _g(["esps", "ntp", "type"]), "icon": "mdi:clock-outline"},
    {"key": "work_mode", "name": "工作模式", "getter": _g(["net", "workMode"]), "icon": "mdi:network"},
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Ne36ProDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = build_device_info(coordinator, entry)
    async_add_entities(
        Ne36ProSensor(coordinator, entry, device, spec) for spec in SENSORS
    )


class Ne36ProSensor(CoordinatorEntity, SensorEntity):
    """A single NE36Pro sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, device, spec: dict) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._spec = spec
        self._getter: _S = spec["getter"]
        self._attr_unique_id = f"{entry.entry_id}_{spec['key']}"
        self._attr_name = spec["name"]
        self._attr_icon = spec.get("icon")
        self._attr_native_unit_of_measurement = spec.get("unit")
        self._attr_device_class = spec.get("device_class")
        self._attr_state_class = spec.get("state_class")
        self._attr_device_info = device

    @property
    def native_value(self):
        try:
            value = self._getter(self.coordinator.data)
        except Exception:  # noqa: BLE001
            return None
        if self._spec.get("kind") == "uptime":
            return _fmt_uptime(value)
        return value
