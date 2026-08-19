"""Base entities for RepRapFirmware."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import RepRapFirmwareConfigEntry
from .const import DOMAIN
from .coordinator import RepRapFirmwareCoordinator


class RepRapFirmwareEntity(CoordinatorEntity[RepRapFirmwareCoordinator]):
    """Base class for entities belonging to one RepRapFirmware printer."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RepRapFirmwareCoordinator,
        entry: RepRapFirmwareConfigEntry,
        entity_key: str,
    ) -> None:
        """Initialize a RepRapFirmware entity."""
        super().__init__(coordinator)
        self._entry = entry
        stable_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{stable_id}_{entity_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the Home Assistant device metadata."""
        data = self.coordinator.data
        stable_id = self._entry.unique_id or self._entry.entry_id
        return DeviceInfo(
            identifiers={(DOMAIN, stable_id)},
            name=self._entry.title,
            model=data.board_name,
            sw_version=data.firmware_version,
            serial_number=data.board_unique_id,
            configuration_url=self.coordinator.client.base_url,
        )
