"""Event platform for RepRapFirmware printer transitions."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RepRapFirmwareConfigEntry
from .const import PRINTER_EVENT_TYPES
from .entity import RepRapFirmwareEntity
from .events import RepRapFirmwareEventTracker


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RepRapFirmwareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the RepRapFirmware printer event entity."""
    async_add_entities([RepRapFirmwarePrinterEvent(entry)])


class RepRapFirmwarePrinterEvent(RepRapFirmwareEntity, EventEntity):
    """Expose one-shot printer lifecycle transitions as an HA event entity."""

    _attr_event_types = list(PRINTER_EVENT_TYPES)
    _attr_translation_key = "printer_event"

    def __init__(self, entry: RepRapFirmwareConfigEntry) -> None:
        """Initialize the printer event entity."""
        coordinator = entry.runtime_data
        super().__init__(coordinator, entry, "printer_event")
        self._tracker = RepRapFirmwareEventTracker(
            coordinator.data,
            initial_online=coordinator.last_update_success,
        )

    @property
    def available(self) -> bool:
        """Keep the event entity available so connection-loss events are visible."""
        return True

    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator results after the entity is registered."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_listener(self._async_handle_coordinator_update)
        )

    @callback
    def _async_handle_coordinator_update(self) -> None:
        """Convert coordinator state transitions into event-entity updates."""
        events = self._tracker.process(
            self.coordinator.data,
            is_online=self.coordinator.last_update_success,
        )
        for event in events:
            self._trigger_event(event.event_type, event.as_event_data())
            self.async_write_ha_state()
