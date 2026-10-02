"""Switch platform for the H3C Magic NE36Pro integration (WiFi on/off)."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Ne36ProDataUpdateCoordinator, build_device_info, radio_field


SWITCHES = [
    {"key": "wifi_2g", "name": "WiFi 2.4G", "radio": "2.4G"},
    {"key": "wifi_5g", "name": "WiFi 5G", "radio": "5G"},
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Ne36ProDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = build_device_info(coordinator, entry)
    async_add_entities(
        Ne36ProWifiSwitch(hass, coordinator, entry, device, spec) for spec in SWITCHES
    )


class Ne36ProWifiSwitch(CoordinatorEntity, SwitchEntity):
    """Toggle a WiFi radio band."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:wifi"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, coordinator, entry, device, spec: dict) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._radio = spec["radio"]
        self._attr_unique_id = f"{entry.entry_id}_{spec['key']}"
        self._attr_name = spec["name"]
        self._attr_device_info = device

    @property
    def is_on(self):
        return radio_field(self.coordinator.data, self._radio, "status") == "enable"

    async def _set(self, state: str) -> None:
        api = self._hass.data[DOMAIN][self._entry.entry_id]["api"]
        await api.set_wifi({self._radio: state})
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        await self._set("enable")

    async def async_turn_off(self, **kwargs) -> None:
        await self._set("disable")
