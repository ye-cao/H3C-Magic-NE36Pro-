"""H3C Magic NE36Pro API client.

Verified against firmware NE36ProV100R002 (device 192.168.101.247):

Auth : POST /api/login/auth {username, password} -> data.session
       subsequent /api/esps use header AUTHENTICATION: <session>
RPC  : POST /api/esps with a JSON array of
       {"object":"esps.x", "method":"y", "id":N, "param":{}}
       response is an array of {"id":N, "result":{"code":0,"message":..,"data":..}}
       (when auth fails the response is a single {"code":7,"message":"Auth Failed"})
Read : esps.system.basicinfo.fwinfo -> data.fwVersion
       esps.system.runtime.{cpurate,memrate,runtimeinfo}
       esps.sta.{getnum,getlist}
       esps.wifi.getssid  param {"list":[{"radio":"2.4G","index":"SSID1"},{"radio":"5G","index":"SSID1"}]}
       esps.system.ntp.get / esps.system.led.get
Write: esps.system.reboot {}
       esps.wifi.setssid {"list":[...]}  (modify status enable/disable)
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

HTTP_TIMEOUT = 15


class Ne36ProAuthError(Exception):
    """Raised when login or an authenticated call fails with code 7."""


class Ne36ProApi:
    """Async client for the H3C Magic NE36Pro JSON-RPC API."""

    def __init__(self, host: str, username: str, password: str, session: aiohttp.ClientSession) -> None:
        self.host = host
        self.username = username
        self.password = password
        self._session = session
        self._token: str | None = None

    def _url(self, path: str) -> str:
        return f"http://{self.host}{path}"

    async def login(self) -> str:
        """Authenticate and store the session token."""
        async with asyncio.timeout(HTTP_TIMEOUT):
            async with self._session.post(
                self._url("/api/login/auth"),
                json={"username": self.username, "password": self.password},
                headers={"Content-Type": "application/json"},
            ) as resp:
                data = await resp.json()
        if data.get("code") != 0 or not (data.get("data") or {}).get("session"):
            raise Ne36ProAuthError(f"login failed: {data}")
        self._token = data["data"]["session"]
        return self._token

    async def _esps_one(self, call: dict):
        """Run a single esps RPC. Returns the `data` payload or None.

        NOTE: the endpoint requires the body to be a JSON ARRAY even for a
        single call: [{"object":..,"method":..,"id":1,"param":{}}]. A bare
        object is rejected with an empty response.
        """
        if not self._token:
            raise Ne36ProAuthError("not logged in")
        payload = [{
            "object": call["object"],
            "method": call["method"],
            "id": 1,
            "param": call.get("param") or {},
        }]
        headers = {"Content-Type": "application/json", "AUTHENTICATION": self._token}
        async with asyncio.timeout(HTTP_TIMEOUT):
            async with self._session.post(
                self._url("/api/esps"), json=payload, headers=headers
            ) as resp:
                raw = await resp.json()
        if isinstance(raw, dict) and raw.get("code") == 7:
            raise Ne36ProAuthError("Auth Failed")
        if isinstance(raw, list) and raw:
            res = raw[0].get("result", {})
        elif isinstance(raw, dict):
            res = raw
        else:
            res = {}
        return res.get("data") if res.get("code") == 0 else None

    async def esps(self, calls: list[dict]) -> dict:
        """Run RPCs concurrently (one HTTP request each).

        NOTE: the router's /api/esps endpoint misbehaves with large arrays
        (a 9-call batch returned a single result), so we send one request per
        call and gather them. Re-login once on auth failure.
        """
        async def _run():
            return await asyncio.gather(*(self._esps_one(c) for c in calls))

        try:
            results = await _run()
        except Ne36ProAuthError:
            await self.login()
            results = await _run()
        return {c["key"]: r for c, r in zip(calls, results)}

    async def wizard(self, name: str) -> dict:
        """Unauthenticated GET on /api/wizard/<name>."""
        async with asyncio.timeout(HTTP_TIMEOUT):
            async with self._session.get(
                self._url(f"/api/wizard/{name}"),
                headers={"Content-Type": "application/json"},
            ) as resp:
                data = await resp.json()
        return data.get("data") or {}

    async def set_wifi(self, radio_status: dict[str, str]) -> None:
        """Toggle WiFi bands. radio_status maps radio->'enable'/'disable'."""
        cur = await self.esps(
            [
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
                }
            ]
        )
        ssid_data = (cur or {}).get("ssid") or {}
        lst = ssid_data.get("list", []) or []
        new_list = []
        for x in lst:
            item = dict(x)
            if item.get("radio") in radio_status:
                item["status"] = radio_status[item["radio"]]
            new_list.append(item)
        if not new_list:
            new_list = [
                {"radio": r, "index": "SSID1", "status": s}
                for r, s in radio_status.items()
            ]
        await self.esps(
            [{"key": "set", "object": "esps.wifi", "method": "setssid", "param": {"list": new_list}}]
        )

    async def reboot(self) -> None:
        """Reboot the device."""
        await self.esps([{"key": "reboot", "object": "esps.system", "method": "reboot", "param": {}}])
