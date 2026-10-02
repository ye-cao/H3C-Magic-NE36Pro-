"""Device tracker platform for the H3C Magic NE36Pro integration.

One presence entity per connected client, built from esps.sta.getlist.
New clients are added automatically on the next coordinator refresh.

NOTE: ScannerEntity (not TrackerEntity) is the correct base for router
presence tracking: ScannerEntity.state is STATE_HOME/STATE_NOT_HOME driven
by is_connected. TrackerEntity.state is purely location-based and ignores
is_connected entirely. ScannerEntity.device_info is @final None by design,
so trackers intentionally do not attach to the router device.
"""
from __future__ import annotations

from homeassistant.components.device_tracker import ScannerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Ne36ProDataUpdateCoordinator


def _clients(data: dict) -> list:
    stalist = (data.get("esps", {}) or {}).get("stalist") or {}
    if isinstance(stalist, dict):
        return stalist.get("list", []) or []
    return []


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: Ne36ProDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    trackers: dict[str, "Ne36ProDeviceTracker"] = {}

    def _sync() -> None:
        new = []
        for c in _clients(coordinator.data):
            mac = c.get("mac")
            if not mac or mac in trackers:
                continue
            ent = Ne36ProDeviceTracker(coordinator, entry, mac)
            trackers[mac] = ent
            new.append(ent)
        if new:
            hass.async_create_task(async_add_entities(new))

    _sync()
    coordinator.async_add_listener(_sync)


class Ne36ProDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Presence tracking for one connected client."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._attr_unique_id = f"{entry.entry_id}_tracker_{mac}"
        self._attr_mac_address = mac

    def _client(self) -> dict | None:
        for c in _clients(self.coordinator.data):
            if c.get("mac") == self._mac:
                return c
        return None

    @property
    def name(self) -> str | None:
        c = self._client()
        if c:
            return c.get("hostname") or c.get("remark") or f"客户端 {self._mac}"
        return f"客户端 {self._mac}"

    @property
    def is_connected(self) -> bool | None:
        c = self._client()
        return bool(c and c.get("isOnline") == "true")

    @property
    def ip_address(self) -> str | None:
        c = self._client()
        return c.get("ip") or None if c else None

    @property
    def hostname(self) -> str | None:
        c = self._client()
        return c.get("hostname") or None if c else None
