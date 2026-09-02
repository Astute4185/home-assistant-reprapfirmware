"""DataUpdateCoordinator for RepRapFirmware."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace
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


def _job_file_size_missing(job: object) -> bool:
    """Return whether an active job object omitted its file size metadata."""
    if not isinstance(job, dict):
        return False
    file_obj = job.get("file")
    if not isinstance(file_obj, dict) or not file_obj.get("fileName"):
        return False
    size = file_obj.get("size")
    return isinstance(size, bool) or not isinstance(size, int) or size <= 0


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
        self._tracked_job_name: str | None = None
        self._tracked_layer: int | None = None
        self._layer_start_extrusion: float | None = None
        self._last_layer_time: float | None = None
        self._observed_layer_time: float | None = None
        self._last_job_duration: float | None = None

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
        """Fetch and normalize the Object Model branches used by HA entities."""
        try:
            state = await self.client.get_model("state")
            # Verbose fields include job.file.size and heater active/standby
            # targets, which are not present in every standard rr_model response.
            job = await self.client.get_model("job", flags="v")
            heat = await self.client.get_model("heat", flags="v")
            tools = await self.client.get_model("tools")
            move = await self.client.get_model("move", flags="v")
            fans = await self.client.get_model("fans")
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

        # These branches add optional diagnostics/features. Failure to read one of
        # them must not make the primary printer entities unavailable.
        live_board: object = {}
        try:
            live_board = await self.client.get_model("boards[0]", flags="v")
        except RepRapFirmwareError as err:
            _LOGGER.debug(
                "Unable to retrieve live RepRapFirmware board diagnostics: %s", err
            )

        filament_monitors: object = []
        try:
            filament_monitors = await self.client.get_model("sensors.filamentMonitors")
        except RepRapFirmwareError as err:
            _LOGGER.debug(
                "Unable to retrieve optional RepRapFirmware filament monitors: %s",
                err,
            )

        board = self._board
        if isinstance(self._board, dict) and isinstance(live_board, dict):
            board = {**self._board, **live_board}
        elif isinstance(live_board, dict) and live_board:
            board = live_board

        file_info: object = {}
        if _job_file_size_missing(job):
            try:
                file_info = await self.client.get_file_info()
            except RepRapFirmwareError as err:
                _LOGGER.debug(
                    "Unable to retrieve optional RepRapFirmware file info: %s", err
                )

        data = parse_printer_data(
            state=state,
            job=job,
            heat=heat,
            tools=tools,
            move=move,
            fans=fans,
            board=board,
            filament_monitors=filament_monitors,
            file_info=file_info,
        )
        data = self._apply_job_tracking(data)
        self.update_interval = (
            ACTIVE_POLL_INTERVAL
            if data.status in ACTIVE_PRINTER_STATES
            else IDLE_POLL_INTERVAL
        )
        return data

    def _apply_job_tracking(self, data: RepRapFirmwareData) -> RepRapFirmwareData:
        """Add values that require tracking successive standalone RRF polls."""
        active_job = data.status in ACTIVE_PRINTER_STATES and data.job_name is not None
        if not active_job:
            self._tracked_job_name = None
            self._tracked_layer = None
            self._layer_start_extrusion = None
            self._last_layer_time = None
            self._observed_layer_time = None
            self._last_job_duration = None
            return replace(data, last_layer_time=None, layer_filament_used=None)

        new_job = self._tracked_job_name != data.job_name
        if (
            not new_job
            and self._last_job_duration is not None
            and data.print_duration is not None
            and data.print_duration < self._last_job_duration
        ):
            new_job = True

        if new_job:
            self._tracked_job_name = data.job_name
            self._tracked_layer = data.layer
            self._layer_start_extrusion = data.filament_used
            self._last_layer_time = None
            self._observed_layer_time = data.layer_time
        elif data.layer is not None:
            if self._tracked_layer is None:
                self._tracked_layer = data.layer
                self._layer_start_extrusion = data.filament_used
                self._observed_layer_time = data.layer_time
            elif data.layer != self._tracked_layer:
                self._last_layer_time = self._observed_layer_time
                self._tracked_layer = data.layer
                self._layer_start_extrusion = data.filament_used
                self._observed_layer_time = data.layer_time
            elif data.layer_time is not None:
                self._observed_layer_time = data.layer_time

        layer_filament_used: float | None = None
        if (
            data.layer is not None
            and data.filament_used is not None
            and self._layer_start_extrusion is not None
        ):
            layer_filament_used = max(
                data.filament_used - self._layer_start_extrusion,
                0.0,
            )

        self._last_job_duration = data.print_duration
        return replace(
            data,
            last_layer_time=self._last_layer_time,
            layer_filament_used=layer_filament_used,
        )

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
        _LOGGER.debug(
            "Discovered %d RepRapFirmware macro(s): %s",
            len(macros),
            ", ".join(macro.name for macro in macros) or "none",
        )
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
        """Resolve a discovered macro by filename, path, or unambiguous .g alias."""
        exact_matches = [macro for macro in self._macros if macro.exact_matches(value)]
        if len(exact_matches) == 1:
            return exact_matches[0]

        alias_matches = [macro for macro in self._macros if macro.matches(value)]
        return alias_matches[0] if len(alias_matches) == 1 else None

    async def async_shutdown(self) -> None:
        """Stop coordinator polling and release the RRF session."""
        await super().async_shutdown()
        try:
            await self.client.disconnect()
        except RepRapFirmwareError:
            _LOGGER.debug("RepRapFirmware session was already unavailable on unload")
