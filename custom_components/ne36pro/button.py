"""Button platform for the H3C Magic NE36Pro integration (reboot)."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Ne36ProDataUpdateCoordinator, build_device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Ne36ProDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    device = build_device_info(coordinator, entry)
    async_add_entities([Ne36ProRebootButton(hass, coordinator, entry, device)])


class Ne36ProRebootButton(CoordinatorEntity, ButtonEntity):
    """Reboot the router."""

    _attr_has_entity_name = True
    _attr_name = "重启"
    _attr_icon = "mdi:restart"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass, coordinator, entry, device) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_reboot"
        self._attr_device_info = device

    async def async_press(self) -> None:
        api = self._hass.data[DOMAIN][self._entry.entry_id]["api"]
        await api.reboot()
