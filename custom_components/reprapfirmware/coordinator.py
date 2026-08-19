"""DataUpdateCoordinator for RepRapFirmware."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RepRapFirmwareClient, RepRapFirmwareError
from .const import (
    ACTIVE_POLL_INTERVAL,
    ACTIVE_PRINTER_STATES,
    DOMAIN,
    IDLE_POLL_INTERVAL,
    MAX_OFFLINE_RETRY_INTERVAL,
    MIN_OFFLINE_RETRY_INTERVAL,
)
from .model import RepRapFirmwareData, parse_printer_data

_LOGGER = logging.getLogger(__name__)


class RepRapFirmwareCoordinator(DataUpdateCoordinator[RepRapFirmwareData]):
    """Coordinate polling of one RepRapFirmware printer."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: RepRapFirmwareClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=IDLE_POLL_INTERVAL,
            always_update=False,
        )
        self.client = client
        self._offline_failures = 0
        self._board: object = {}

    async def _async_setup(self) -> None:
        """Load printer metadata that does not need polling every cycle."""
        try:
            self._board = await self.client.get_model("boards[0]")
        except RepRapFirmwareError as err:
            raise UpdateFailed(
                f"Error reading RepRapFirmware board information: {err}"
            ) from err

    async def _async_update_data(self) -> RepRapFirmwareData:
        """Fetch and normalize the Object Model branches used by P1."""
        try:
            state = await self.client.get_model("state")
            job = await self.client.get_model("job")
            heat = await self.client.get_model("heat")
            tools = await self.client.get_model("tools")
        except RepRapFirmwareError as err:
            self._offline_failures += 1
            retry_after = min(
                MIN_OFFLINE_RETRY_INTERVAL.total_seconds()
                * (2 ** (self._offline_failures - 1)),
                MAX_OFFLINE_RETRY_INTERVAL.total_seconds(),
            )
            raise UpdateFailed(
                f"Error communicating with RepRapFirmware: {err}",
                retry_after=retry_after,
            ) from err

        self._offline_failures = 0
        data = parse_printer_data(
            state=state,
            job=job,
            heat=heat,
            tools=tools,
            board=self._board,
        )
        self.update_interval = (
            ACTIVE_POLL_INTERVAL
            if data.status in ACTIVE_PRINTER_STATES
            else IDLE_POLL_INTERVAL
        )
        return data

    async def async_shutdown(self) -> None:
        """Stop coordinator polling and release the RRF session."""
        await super().async_shutdown()
        try:
            await self.client.disconnect()
        except RepRapFirmwareError:
            _LOGGER.debug("RepRapFirmware session was already unavailable on unload")
