"""RepRapFirmware integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import RepRapFirmwareClient
from .const import CONF_USE_SSL, DOMAIN
from .coordinator import RepRapFirmwareCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.EVENT,
]

type RepRapFirmwareConfigEntry = ConfigEntry[RepRapFirmwareCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up RepRapFirmware integration-level service actions."""
    async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: RepRapFirmwareConfigEntry
) -> bool:
    """Set up RepRapFirmware from a config entry."""
    client = RepRapFirmwareClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        use_ssl=entry.data[CONF_USE_SSL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )
    coordinator = RepRapFirmwareCoordinator(hass, entry, client)
    entry.runtime_data = coordinator

    await coordinator.async_config_entry_first_refresh()

    # P0 used host:port as the config-entry unique ID. Migrate those development
    # entries to the main board's stable hardware ID before entities are created.
    board_unique_id = coordinator.data.board_unique_id
    legacy_unique_id = f"{entry.data[CONF_HOST].lower()}:{entry.data[CONF_PORT]}"
    if board_unique_id and entry.unique_id in (None, legacy_unique_id):
        existing = hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, board_unique_id
        )
        if existing is None or existing.entry_id == entry.entry_id:
            hass.config_entries.async_update_entry(entry, unique_id=board_unique_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RepRapFirmwareConfigEntry
) -> bool:
    """Unload a RepRapFirmware config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
