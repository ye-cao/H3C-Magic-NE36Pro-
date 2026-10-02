"""DataUpdateCoordinator for the H3C Magic NE36Pro integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import Ne36ProApi, Ne36ProAuthError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Single batch of read RPCs (one HTTP call).
_READ_CALLS = [
    {"key": "fwinfo", "object": "esps.system.basicinfo", "method": "fwinfo"},
    {"key": "cpu", "object": "esps.system.runtime", "method": "cpurate"},
    {"key": "mem", "object": "esps.system.runtime", "method": "memrate"},
    {"key": "rt", "object": "esps.system.runtime", "method": "runtimeinfo"},
    {"key": "stanum", "object": "esps.sta", "method": "getnum"},
    {"key": "stalist", "object": "esps.sta", "method": "getlist"},
    {
        "key": "ssid",
        "object": "esps.wifi",
        "method": "getssid",
        "param": {
            "list": [
                {"radio": "2.4G", "index": "SSID1"},
                {"radio": "5G", "index": "SSID1"},
            ]
        },
    },
    {"key": "ntp", "object": "esps.system.ntp", "method": "get"},
    {"key": "led", "object": "esps.system.led", "method": "get"},
]


class Ne36ProDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinate polling of the router."""

    def __init__(self, hass, api: Ne36ProApi, entry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            config_entry=entry,
        )
        self.api = api

    async def _async_update_data(self) -> dict:
        try:
            basic = await self.api.wizard("getBasicInfo") or {}
            net = await self.api.wizard("getNetworkStatus") or {}
            esps = await self.api.esps(_READ_CALLS)
        except Ne36ProAuthError as err:
            raise UpdateFailed(f"Auth error: {err}") from err
        except Exception as err:  # noqa: BLE001 - surface any comms error to HA
            raise UpdateFailed(f"Communication error: {err}") from err
        return {"basic": basic, "net": net, "esps": esps}


def ssid_list(data: dict) -> list:
    esps = data.get("esps", {})
    ssid = esps.get("ssid") or {}
    return ssid.get("list", []) if isinstance(ssid, dict) else []


def radio_field(data: dict, radio: str, field: str):
    for x in ssid_list(data):
        if x.get("radio") == radio:
            return x.get(field)
    return None


def build_device_info(coordinator: "Ne36ProDataUpdateCoordinator", entry) -> dict:
    """Build the DeviceInfo linking every entity to one device."""
    from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

    data = coordinator.data or {}
    basic = data.get("basic", {}) or {}
    esps = data.get("esps", {}) or {}
    fw = (esps.get("fwinfo") or {}).get("fwVersion")
    mac = basic.get("mac")
    connections = {(CONNECTION_NETWORK_MAC, mac)} if mac else None
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="H3C Magic NE36Pro",
        manufacturer="H3C",
        model=basic.get("model"),
        sw_version=fw,
        connections=connections,
    )
