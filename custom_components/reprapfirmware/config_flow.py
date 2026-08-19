"""Config flow for RepRapFirmware."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_USE_SSL,
    DEFAULT_NAME,
    DEFAULT_PORT_HTTP,
    DOMAIN,
)


class RepRapFirmwareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RepRapFirmware."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step.

        Connection validation will be added with the P0 API client.
        """
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]

            await self.async_set_unique_id(f"{host.lower()}:{port}")
            self._abort_if_unique_id_configured()

            data = {
                **user_input,
                CONF_HOST: host,
            }
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or host,
                data=data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT_HTTP): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_USE_SSL, default=False): bool,
                vol.Required(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
