"""DataUpdateCoordinator for RepRapFirmware."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RepRapFirmwareClient, RepRapFirmwareError
from .const import (
    ACTIVE_POLL_INTERVAL,
    ACTIVE_PRINTER_STATES,
    DOMAIN,
    IDLE_POLL_INTERVAL,
    MACRO_DIRECTORY,
    MACRO_REFRESH_INTERVAL,
    MAX_OFFLINE_RETRY_INTERVAL,
    MIN_OFFLINE_RETRY_INTERVAL,
)
from .macro import RepRapFirmwareMacro, discover_macros
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
        self._entry = entry
        self._offline_failures = 0
        self._board: object = {}
        self._macros: tuple[RepRapFirmwareMacro, ...] = ()
        self._macro_listeners: set[Callable[[], None]] = set()

    @property
    def macros(self) -> tuple[RepRapFirmwareMacro, ...]:
        """Return the currently discovered top-level macros."""
        return self._macros

    async def _async_setup(self) -> None:
        """Load printer metadata and initial macro discovery."""
        try:
            self._board = await self.client.get_model("boards[0]")
        except RepRapFirmwareError as err:
            raise UpdateFailed(
                f"Error reading RepRapFirmware board information: {err}"
            ) from err

        await self.async_refresh_macros()
        self._entry.async_on_unload(
            async_track_time_interval(
                self.hass,
                self._async_periodic_macro_refresh,
                MACRO_REFRESH_INTERVAL,
            )
        )

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

    async def async_refresh_macros(self) -> bool:
        """Refresh discovered macros without making printer state unavailable."""
        try:
            items = await self.client.list_files(MACRO_DIRECTORY)
        except RepRapFirmwareError as err:
            _LOGGER.warning("Unable to refresh RepRapFirmware macros: %s", err)
            return False

        macros = discover_macros(items)
        if macros == self._macros:
            return True

        self._macros = macros
        for listener in tuple(self._macro_listeners):
            listener()
        return True

    async def _async_periodic_macro_refresh(self, _now: datetime) -> None:
        """Refresh macros on the low-frequency discovery interval."""
        await self.async_refresh_macros()

    @callback
    def async_add_macro_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        """Register a callback for macro-list changes."""
        self._macro_listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._macro_listeners.discard(listener)

        return remove_listener

    def macro_by_name_or_path(self, value: str) -> RepRapFirmwareMacro | None:
        """Resolve a discovered macro by its filename or full macro path."""
        value = value.strip()
        return next(
            (
                macro
                for macro in self._macros
                if value == macro.name or value == macro.path
            ),
            None,
        )

    async def async_shutdown(self) -> None:
        """Stop coordinator polling and release the RRF session."""
        await super().async_shutdown()
        try:
            await self.client.disconnect()
        except RepRapFirmwareError:
            _LOGGER.debug("RepRapFirmware session was already unavailable on unload")
