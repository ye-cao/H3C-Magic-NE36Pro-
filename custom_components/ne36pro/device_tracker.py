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
    stalist = (data.get("esps", {}) or {}).get("stalist")
    if isinstance(stalist, dict):
        return stalist.get("list", []) or []
    if isinstance(stalist, list):  # defensive: some firmwares return a bare array
        return stalist
    return []


def _is_online(c: dict) -> bool:
    # firmware returns the string "true"; accept native bools too
    return c.get("isOnline") in ("true", True)


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
            # Modern HA: async_add_entities is a plain callback returning None
            # (schedules internally); wrapping it in async_create_task raises
            # "a coroutine was expected, got None".
            async_add_entities(new)

    _sync()
    coordinator.async_add_listener(_sync)


class Ne36ProDeviceTracker(CoordinatorEntity, ScannerEntity):
    """Presence tracking for one connected client."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tracker_{mac}"
        self._attr_mac_address = mac

    def _client(self) -> dict | None:
        for c in _clients(self.coordinator.data):
            if c.get("mac") == self._mac:
                return c
        return None

    @property
    def name(self) -> str | None:
        c = self._client() or {}
        return (
            c.get("hostname")
            or c.get("remark")
            or (f"{c.get('brand')} 设备" if c.get("brand") else None)
            or f"客户端 {self._mac}"
        )

    @property
    def is_connected(self) -> bool | None:
        c = self._client()
        return bool(c and _is_online(c))

    @property
    def ip_address(self) -> str | None:
        c = self._client()
        return (c.get("ip") or None) if c else None

    @property
    def hostname(self) -> str | None:
        c = self._client()
        return (c.get("hostname") or None) if c else None

    @property
    def extra_state_attributes(self) -> dict | None:
        """Expose connection details so 2.4G/5G clients are distinguishable."""
        c = self._client()
        if not c:
            return None
        attrs = {}
        for src, dst in (
            ("ssid", "ssid"),
            ("linkType", "link_type"),
            ("channel", "channel"),
            ("rssi", "rssi"),
            ("signLevel", "signal_level"),
            ("brand", "brand"),
            ("model", "model"),
            ("isWifi6", "wifi6"),
            ("isWifi7", "wifi7"),
            ("onlineTime", "online_time"),
            ("upRemark", "uplink"),
        ):
            v = c.get(src)
            if v not in (None, ""):
                attrs[dst] = v
        return attrs or None
