"""Sensor platform for RepRapFirmware."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfInformation,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RepRapFirmwareConfigEntry
from .coordinator import RepRapFirmwareCoordinator
from .entity import RepRapFirmwareEntity
from .model import RepRapFirmwareData


@dataclass(frozen=True, kw_only=True)
class RepRapFirmwareSensorEntityDescription(SensorEntityDescription):
    """Description of a RepRapFirmware sensor."""

    value_fn: Callable[[RepRapFirmwareData], StateType]


SENSORS: tuple[RepRapFirmwareSensorEntityDescription, ...] = (
    RepRapFirmwareSensorEntityDescription(
        key="status",
        translation_key="status",
        value_fn=lambda data: data.status,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="job_name",
        translation_key="job_name",
        value_fn=lambda data: data.job_name,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="progress",
        translation_key="progress",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.progress,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="print_duration",
        translation_key="print_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.print_duration,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="estimated_remaining",
        translation_key="estimated_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.estimated_remaining,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="layer",
        translation_key="layer",
        value_fn=lambda data: data.layer,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="file_size",
        translation_key="file_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        value_fn=lambda data: data.file_size,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.nozzle_temperature,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="nozzle_target",
        translation_key="nozzle_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.nozzle_target,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="bed_temperature",
        translation_key="bed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.bed_temperature,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="bed_target",
        translation_key="bed_target",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.bed_target,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="x_position",
        translation_key="x_position",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.x_position,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="y_position",
        translation_key="y_position",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.y_position,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="z_position",
        translation_key="z_position",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.z_position,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="current_tool",
        translation_key="current_tool",
        value_fn=lambda data: data.current_tool,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.fan_speed,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="speed_factor",
        translation_key="speed_factor",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.speed_factor,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RepRapFirmwareConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RepRapFirmware sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        RepRapFirmwareSensor(coordinator, entry, description) for description in SENSORS
    )


class RepRapFirmwareSensor(RepRapFirmwareEntity, SensorEntity):
    """Representation of a RepRapFirmware sensor."""

    entity_description: RepRapFirmwareSensorEntityDescription

    def __init__(
        self,
        coordinator: RepRapFirmwareCoordinator,
        entry: RepRapFirmwareConfigEntry,
        description: RepRapFirmwareSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the latest value from coordinator memory."""
        return self.entity_description.value_fn(self.coordinator.data)
