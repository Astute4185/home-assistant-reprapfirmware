"""Config flow for RepRapFirmware."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    RepRapFirmwareAuthenticationError,
    RepRapFirmwareClient,
    RepRapFirmwareError,
)
from .const import CONF_USE_SSL, DEFAULT_NAME, DEFAULT_PORT_HTTP, DOMAIN

_LOGGER = logging.getLogger(__name__)


class RepRapFirmwareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RepRapFirmware."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            board_unique_id: str | None = None
            client = RepRapFirmwareClient(
                host=host,
                port=port,
                use_ssl=user_input[CONF_USE_SSL],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )

            try:
                await client.connect()
                await client.get_model("state")
                board = await client.get_model("boards[0]")
                if isinstance(board, dict):
                    unique_id = board.get("uniqueId")
                    if isinstance(unique_id, str) and unique_id.strip():
                        board_unique_id = unique_id.strip()
            except RepRapFirmwareAuthenticationError:
                errors["base"] = "invalid_auth"
            except RepRapFirmwareError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating RepRapFirmware endpoint")
                errors["base"] = "unknown"
            finally:
                with suppress(RepRapFirmwareError):
                    await client.disconnect()

            if not errors:
                if board_unique_id is not None:
                    await self.async_set_unique_id(board_unique_id)
                    self._abort_if_unique_id_configured()
                else:
                    self._async_abort_entries_match(
                        {
                            CONF_HOST: host,
                            CONF_PORT: port,
                            CONF_USE_SSL: user_input[CONF_USE_SSL],
                        }
                    )

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

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
