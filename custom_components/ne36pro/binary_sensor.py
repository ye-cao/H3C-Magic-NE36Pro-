"""Binary sensor platform for the H3C Magic NE36Pro integration."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Ne36ProDataUpdateCoordinator, build_device_info, radio_field


def _wifi_enabled(radio: str):
    def getter(data: dict):
        return radio_field(data, radio, "status") == "enable"
    return getter


def _led_enabled(data: dict):
    return (data.get("esps", {}).get("led") or {}).get("status") == "enable"


BINARY_SENSORS: list[dict] = [
    {"key": "wifi_2g", "name": "WiFi 2.4G 已启用", "getter": _wifi_enabled("2.4G"), "device_class": BinarySensorDeviceClass.CONNECTIVITY},
    {"key": "wifi_5g", "name": "WiFi 5G 已启用", "getter": _wifi_enabled("5G"), "device_class": BinarySensorDeviceClass.CONNECTIVITY},
    {"key": "led", "name": "指示灯", "getter": _led_enabled, "device_class": BinarySensorDeviceClass.RUNNING},
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Ne36ProDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = build_device_info(coordinator, entry)
    async_add_entities(
        Ne36ProBinarySensor(coordinator, entry, device, spec) for spec in BINARY_SENSORS
    )


class Ne36ProBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A single NE36Pro binary sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, device, spec: dict) -> None:
        super().__init__(coordinator)
        self._getter = spec["getter"]
        self._attr_unique_id = f"{entry.entry_id}_{spec['key']}"
        self._attr_name = spec["name"]
        self._attr_device_class = spec.get("device_class")
        self._attr_device_info = device

    @property
    def is_on(self):
        try:
            return bool(self._getter(self.coordinator.data))
        except Exception:  # noqa: BLE001
            return False
