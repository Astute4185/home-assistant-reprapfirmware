"""Binary sensor platform for RepRapFirmware."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RepRapFirmwareConfigEntry
from .entity import RepRapFirmwareEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RepRapFirmwareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the RepRapFirmware online sensor."""
    async_add_entities([RepRapFirmwareOnlineSensor(entry)])


class RepRapFirmwareOnlineSensor(RepRapFirmwareEntity, BinarySensorEntity):
    """Report whether the printer is responding to coordinator polls."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_translation_key = "online"

    def __init__(self, entry: RepRapFirmwareConfigEntry) -> None:
        """Initialize the online sensor."""
        super().__init__(entry.runtime_data, entry, "online")

    @property
    def available(self) -> bool:
        """Keep the connectivity entity available when the printer is offline."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the last coordinator refresh succeeded."""
        return self.coordinator.last_update_success
