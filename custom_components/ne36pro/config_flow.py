"""Config flow for the H3C Magic NE36Pro integration."""
from __future__ import annotations

import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import Ne36ProApi, Ne36ProAuthError
from .const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, DEFAULT_USERNAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


class Ne36ProConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for H3C Magic NE36Pro."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):  # type: ignore[override]
        errors: dict = {}
        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                api = Ne36ProApi(
                    user_input[CONF_HOST],
                    user_input.get(CONF_USERNAME, DEFAULT_USERNAME),
                    user_input[CONF_PASSWORD],
                    session,
                )
                await api.login()
            except Ne36ProAuthError:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_HOST], data=user_input
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
