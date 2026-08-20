"""Button platform for RepRapFirmware machine controls and macros."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RepRapFirmwareConfigEntry
from .api import RepRapFirmwareError
from .const import DOMAIN
from .control import CONTROL_COMMANDS, RepRapFirmwareControlCommand
from .coordinator import RepRapFirmwareCoordinator
from .entity import RepRapFirmwareEntity
from .macro import RepRapFirmwareMacro


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RepRapFirmwareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RepRapFirmware machine-control and discovered macro buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        RepRapFirmwareControlButton(coordinator, entry, command)
        for command in CONTROL_COMMANDS
    )

    known_macro_paths: set[str] = set()

    @callback
    def async_sync_macro_buttons() -> None:
        new_macros = [
            macro for macro in coordinator.macros if macro.path not in known_macro_paths
        ]
        if not new_macros:
            return
        known_macro_paths.update(macro.path for macro in new_macros)
        async_add_entities(
            RepRapFirmwareMacroButton(coordinator, entry, macro) for macro in new_macros
        )

    async_sync_macro_buttons()
    entry.async_on_unload(
        coordinator.async_add_macro_listener(async_sync_macro_buttons)
    )


class RepRapFirmwareControlButton(RepRapFirmwareEntity, ButtonEntity):
    """State-aware RepRapFirmware machine-control button."""

    def __init__(
        self,
        coordinator: RepRapFirmwareCoordinator,
        entry: RepRapFirmwareConfigEntry,
        command: RepRapFirmwareControlCommand,
    ) -> None:
        """Initialize the control button."""
        super().__init__(coordinator, entry, command.key)
        self._command = command
        self._attr_translation_key = command.key

    @property
    def available(self) -> bool:
        """Return whether the printer can currently execute this command."""
        return super().available and self._command.is_allowed(
            self.coordinator.data.status
        )

    async def async_press(self) -> None:
        """Submit the command and request an immediate state refresh."""
        state = self.coordinator.data.status
        if not self._command.is_allowed(state):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="command_not_allowed",
                translation_placeholders={"state": state or "unknown"},
            )

        try:
            await self.coordinator.client.send_gcode(self._command.gcode)
            await self.coordinator.async_request_refresh()
        except RepRapFirmwareError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err


class RepRapFirmwareMacroButton(RepRapFirmwareEntity, ButtonEntity):
    """Button that executes one discovered RepRapFirmware macro."""

    _attr_icon = "mdi:script-text-play-outline"

    def __init__(
        self,
        coordinator: RepRapFirmwareCoordinator,
        entry: RepRapFirmwareConfigEntry,
        macro: RepRapFirmwareMacro,
    ) -> None:
        """Initialize a discovered macro button."""
        super().__init__(coordinator, entry, macro.entity_key)
        self._macro = macro
        self._attr_name = macro.display_name

    @property
    def available(self) -> bool:
        """Return whether the printer is online and the macro is still discovered."""
        return (
            super().available
            and self.coordinator.macro_by_name_or_path(self._macro.path) is not None
        )

    async def async_press(self) -> None:
        """Execute the discovered macro."""
        if self.coordinator.macro_by_name_or_path(self._macro.path) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="macro_not_found",
                translation_placeholders={"macro": self._macro.name},
            )

        try:
            await self.coordinator.client.send_gcode(self._macro.gcode)
            await self.coordinator.async_request_refresh()
        except RepRapFirmwareError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err
