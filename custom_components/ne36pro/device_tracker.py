"""Device tracker platform for the H3C Magic NE36Pro integration.

One presence entity per connected client, built from esps.sta.getlist.
New clients are added automatically on the next coordinator refresh.

Design note (v1.0.4): ScannerEntity was used before, but its device_info
is @final None — tracker entities could never appear on any device page.
TrackerEntity.state however is NOT final (ScannerEntity itself just
overrides it), so we subclass TrackerEntity, reimplement the scanner
state semantics (home/not_home from the client list) and attach
device_info pointing at the router device. Result: every client shows
up under the "H3C Magic NE36Pro" device card.
"""
from __future__ import annotations

from homeassistant.components.device_tracker import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
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


class Ne36ProDeviceTracker(CoordinatorEntity, TrackerEntity):
    """Presence tracking for one connected client."""

    _attr_has_entity_name = True
    _attr_source_type = SourceType.ROUTER
    # HA's BaseTrackerEntity defaults to EntityCategory.DIAGNOSTIC, which
    # buries client trackers in the device page's "诊断" fold. Client
    # presence belongs on the main device card — override the default.
    _attr_entity_category = None

    def __init__(self, coordinator, entry, mac: str) -> None:
        super().__init__(coordinator)
        self._mac = mac
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_tracker_{mac}"
        self._attr_mac_address = mac
        # Attach to the router device so every client is visible on the
        # "H3C Magic NE36Pro" device card (ScannerEntity forbids this;
        # plain TrackerEntity allows it).
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    def _client(self) -> dict | None:
        for c in _clients(self.coordinator.data):
            if c.get("mac") == self._mac:
                return c
        return None

    @property
    def name(self) -> str | None:
        c = self._client() or {}
        base = (
            c.get("hostname")
            or c.get("remark")
            or (f"{c.get('brand')} 设备" if c.get("brand") else None)
            or "客户端"
        )
        # The router reports many clients with the same generic hostname
        # (e.g. "默认 设备"); append the MAC tail so entities stay
        # distinguishable.
        return f"{base} · {self._mac[-8:]}"

    @property
    def state(self) -> str | None:
        """home/not_home from the client list — scanner semantics."""
        c = self._client()
        if c is None:
            return STATE_NOT_HOME  # client no longer in the list
        return STATE_HOME if _is_online(c) else STATE_NOT_HOME

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
