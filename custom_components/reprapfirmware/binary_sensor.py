"""Binary sensor platform for RepRapFirmware."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RepRapFirmwareConfigEntry
from .coordinator import RepRapFirmwareCoordinator
from .entity import RepRapFirmwareEntity
from .model import RepRapFirmwareData


@dataclass(frozen=True, kw_only=True)
class RepRapFirmwareBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description of a RepRapFirmware binary sensor."""

    value_fn: Callable[[RepRapFirmwareData], bool | None]
    exists_fn: Callable[[RepRapFirmwareData], bool] = lambda _data: True


def _filament_monitor_problem(data: RepRapFirmwareData) -> bool | None:
    """Return whether the configured filament monitor reports a problem."""
    status = data.filament_monitor_status
    if status is None:
        return None
    return status != "ok"


BINARY_SENSORS: tuple[RepRapFirmwareBinarySensorEntityDescription, ...] = (
    RepRapFirmwareBinarySensorEntityDescription(
        key="x_homed",
        translation_key="x_homed",
        value_fn=lambda data: data.x_homed,
    ),
    RepRapFirmwareBinarySensorEntityDescription(
        key="y_homed",
        translation_key="y_homed",
        value_fn=lambda data: data.y_homed,
    ),
    RepRapFirmwareBinarySensorEntityDescription(
        key="z_homed",
        translation_key="z_homed",
        value_fn=lambda data: data.z_homed,
    ),
    RepRapFirmwareBinarySensorEntityDescription(
        key="filament_monitor",
        translation_key="filament_monitor",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value_fn=_filament_monitor_problem,
        exists_fn=lambda data: data.filament_monitor_status is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RepRapFirmwareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RepRapFirmware binary sensors from a config entry."""
    coordinator = entry.runtime_data
    static_descriptions = [
        description
        for description in BINARY_SENSORS
        if description.key != "filament_monitor"
    ]
    async_add_entities(
        [RepRapFirmwareOnlineSensor(entry)]
        + [
            RepRapFirmwareBinarySensor(coordinator, entry, description)
            for description in static_descriptions
        ]
    )

    monitor_description = next(
        description
        for description in BINARY_SENSORS
        if description.key == "filament_monitor"
    )
    monitor_added = False

    @callback
    def add_filament_monitor_if_present() -> None:
        nonlocal monitor_added
        if monitor_added or not monitor_description.exists_fn(coordinator.data):
            return
        monitor_added = True
        async_add_entities(
            [RepRapFirmwareBinarySensor(coordinator, entry, monitor_description)]
        )

    add_filament_monitor_if_present()
    entry.async_on_unload(
        coordinator.async_add_listener(add_filament_monitor_if_present)
    )


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


class RepRapFirmwareBinarySensor(RepRapFirmwareEntity, BinarySensorEntity):
    """Representation of a RepRapFirmware binary sensor."""

    entity_description: RepRapFirmwareBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: RepRapFirmwareCoordinator,
        entry: RepRapFirmwareConfigEntry,
        description: RepRapFirmwareBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the latest binary value from coordinator memory."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Expose the raw RRF filament-monitor status when applicable."""
        if self.entity_description.key != "filament_monitor":
            return None
        status = self.coordinator.data.filament_monitor_status
        return {"status": status} if status is not None else None
