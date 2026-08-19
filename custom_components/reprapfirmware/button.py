"""Button platform for RepRapFirmware machine controls."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RepRapFirmwareConfigEntry
from .api import RepRapFirmwareError
from .const import DOMAIN
from .control import CONTROL_COMMANDS, RepRapFirmwareControlCommand
from .coordinator import RepRapFirmwareCoordinator
from .entity import RepRapFirmwareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RepRapFirmwareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RepRapFirmware machine-control buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        RepRapFirmwareControlButton(coordinator, entry, command)
        for command in CONTROL_COMMANDS
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
