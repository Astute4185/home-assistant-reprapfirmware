"""Config flow for RepRapFirmware."""

from __future__ import annotations

import logging
from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    RepRapFirmwareAuthenticationError,
    RepRapFirmwareClient,
    RepRapFirmwareError,
)
from .const import (
    CONF_OBJECT_MODEL_ENTITY_TYPE,
    CONF_OBJECT_MODEL_INVERT,
    CONF_OBJECT_MODEL_NAME,
    CONF_OBJECT_MODEL_PATH,
    CONF_OBJECT_MODEL_UNIT,
    CONF_USE_SSL,
    DEFAULT_NAME,
    DEFAULT_PORT_HTTP,
    DOMAIN,
    ENTITY_TYPE_BINARY_SENSOR,
    ENTITY_TYPE_SENSOR,
    MAX_OBJECT_MODEL_ENTITIES,
)
from .object_model import (
    build_object_model_config,
    is_object_model_scalar,
    object_model_binary_value,
    object_model_configs_from_options,
    options_with_object_model_configs,
)

_LOGGER = logging.getLogger(__name__)


class RepRapFirmwareConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RepRapFirmware."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RepRapFirmwareOptionsFlow:
        """Return the options flow for configurable Object Model entities."""
        return RepRapFirmwareOptionsFlow()

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


class RepRapFirmwareOptionsFlow(OptionsFlowWithReload):
    """Manage optional RepRapFirmware Object Model entities."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the Object Model entity management menu."""
        configs = object_model_configs_from_options(self.config_entry.options)
        menu_options: list[str] = []
        if len(configs) < MAX_OBJECT_MODEL_ENTITIES:
            menu_options.append("add_object_model_entity")
        if configs:
            menu_options.append("remove_object_model_entity")

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    async def async_step_add_object_model_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add one scalar RepRapFirmware Object Model entity."""
        errors: dict[str, str] = {}
        configs = object_model_configs_from_options(self.config_entry.options)

        if len(configs) >= MAX_OBJECT_MODEL_ENTITIES:
            return self.async_abort(reason="object_model_limit_reached")

        if user_input is not None:
            try:
                config = build_object_model_config(
                    path=user_input[CONF_OBJECT_MODEL_PATH],
                    name=user_input[CONF_OBJECT_MODEL_NAME],
                    entity_type=user_input[CONF_OBJECT_MODEL_ENTITY_TYPE],
                    unit=user_input.get(CONF_OBJECT_MODEL_UNIT),
                    invert=user_input.get(CONF_OBJECT_MODEL_INVERT, False),
                )
            except TypeError, ValueError:
                errors["base"] = "invalid_object_model_config"
            else:
                if any(existing.path == config.path for existing in configs):
                    errors[CONF_OBJECT_MODEL_PATH] = "object_model_path_exists"
                else:
                    validation_error = await self._async_validate_live_path(config)
                    if validation_error is not None:
                        errors["base"] = validation_error
                    else:
                        options = options_with_object_model_configs(
                            self.config_entry.options,
                            [*configs, config],
                        )
                        return self.async_create_entry(data=options)

        schema = vol.Schema(
            {
                vol.Required(CONF_OBJECT_MODEL_PATH): str,
                vol.Required(CONF_OBJECT_MODEL_NAME): str,
                vol.Required(
                    CONF_OBJECT_MODEL_ENTITY_TYPE,
                    default=ENTITY_TYPE_SENSOR,
                ): vol.In(
                    {
                        ENTITY_TYPE_SENSOR: "Sensor",
                        ENTITY_TYPE_BINARY_SENSOR: "Binary sensor",
                    }
                ),
                vol.Optional(CONF_OBJECT_MODEL_UNIT, default=""): str,
                vol.Optional(CONF_OBJECT_MODEL_INVERT, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="add_object_model_entity",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_remove_object_model_entity(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove one configured Object Model entity."""
        configs = object_model_configs_from_options(self.config_entry.options)
        if not configs:
            return self.async_abort(reason="no_object_model_entities")

        if user_input is not None:
            selected_path = user_input[CONF_OBJECT_MODEL_PATH]
            remaining = [config for config in configs if config.path != selected_path]
            options = options_with_object_model_configs(
                self.config_entry.options,
                remaining,
            )
            return self.async_create_entry(data=options)

        choices = {config.path: f"{config.name} ({config.path})" for config in configs}
        return self.async_show_form(
            step_id="remove_object_model_entity",
            data_schema=vol.Schema(
                {vol.Required(CONF_OBJECT_MODEL_PATH): vol.In(choices)}
            ),
        )

    async def _async_validate_live_path(self, config: Any) -> str | None:
        """Validate the current value when the config entry is loaded."""
        coordinator = getattr(self.config_entry, "runtime_data", None)
        if coordinator is None:
            return None

        try:
            value = await coordinator.client.get_model(config.path)
        except RepRapFirmwareError:
            return "cannot_read_object_model_path"

        if not is_object_model_scalar(value):
            return "object_model_value_not_scalar"
        if (
            config.entity_type == ENTITY_TYPE_BINARY_SENSOR
            and value is not None
            and object_model_binary_value(value) is None
        ):
            return "object_model_value_not_binary"
        if config.entity_type == ENTITY_TYPE_SENSOR and isinstance(value, bool):
            return "object_model_value_is_boolean"
        return None
