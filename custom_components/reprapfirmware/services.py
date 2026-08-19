"""Service actions for RepRapFirmware."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .api import RepRapFirmwareError
from .const import ATTR_GCODE, DOMAIN, SERVICE_SEND_GCODE
from .coordinator import RepRapFirmwareCoordinator


def _non_empty_gcode(value: str) -> str:
    """Validate and normalize an arbitrary G-code payload."""
    value = value.strip()
    if not value:
        raise vol.Invalid("gcode must not be empty")
    return value


SEND_GCODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_GCODE): vol.All(cv.string, _non_empty_gcode),
    }
)


def _coordinator_for_device(
    hass: HomeAssistant, device_id: str
) -> RepRapFirmwareCoordinator:
    """Resolve a loaded RepRapFirmware coordinator from a HA device ID."""
    registry = dr.async_get(hass)
    device = registry.async_get(device_id)
    if device is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_device_id",
            translation_placeholders={"device_id": device_id},
        )

    entry = hass.config_entries.async_get_entry(device.config_entry_id)
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
        or not isinstance(entry.runtime_data, RepRapFirmwareCoordinator)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )

    return entry.runtime_data


async def async_send_gcode(call: ServiceCall) -> ServiceResponse:
    """Send arbitrary G-code to one configured RepRapFirmware printer."""
    coordinator = _coordinator_for_device(call.hass, call.data[ATTR_DEVICE_ID])

    try:
        result = await coordinator.client.send_gcode(
            call.data[ATTR_GCODE],
            wait_for_reply=call.return_response,
        )
        await coordinator.async_request_refresh()
    except RepRapFirmwareError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
        ) from err

    if not call.return_response:
        return None

    return {
        "buffer_space": result.buffer_space,
        "reply": result.reply,
    }


def async_setup_services(hass: HomeAssistant) -> None:
    """Register RepRapFirmware service actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_GCODE,
        async_send_gcode,
        schema=SEND_GCODE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
