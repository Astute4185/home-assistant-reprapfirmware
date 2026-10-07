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
    UnitOfElectricPotential,
    UnitOfInformation,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
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
    attributes_fn: Callable[[RepRapFirmwareData], dict[str, StateType]] | None = None


def _heater_attributes(state: str | None) -> dict[str, StateType]:
    """Expose the RRF heater state without creating another sensor entity."""
    return {"heater_state": state} if state is not None else {}


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
        key="estimated_remaining_filament",
        translation_key="estimated_remaining_filament",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.estimated_remaining_filament,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="estimated_remaining_file",
        translation_key="estimated_remaining_file",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.estimated_remaining_file,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="estimated_remaining_slicer",
        translation_key="estimated_remaining_slicer",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.estimated_remaining_slicer,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="warm_up_duration",
        translation_key="warm_up_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.warm_up_duration,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="layer_time",
        translation_key="layer_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.layer_time,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="last_layer_time",
        translation_key="last_layer_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.last_layer_time,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="layer",
        translation_key="layer",
        value_fn=lambda data: data.layer,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="total_layers",
        translation_key="total_layers",
        value_fn=lambda data: data.total_layers,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="layers_remaining",
        translation_key="layers_remaining",
        value_fn=lambda data: data.layers_remaining,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="file_size",
        translation_key="file_size",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        value_fn=lambda data: data.file_size,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="filament_used",
        translation_key="filament_used",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=lambda data: data.filament_used,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="total_filament",
        translation_key="total_filament",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=lambda data: data.total_filament,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="filament_remaining",
        translation_key="filament_remaining",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=lambda data: data.filament_remaining,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="layer_filament_used",
        translation_key="layer_filament_used",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=lambda data: data.layer_filament_used,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="nozzle_temperature",
        translation_key="nozzle_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.nozzle_temperature,
        attributes_fn=lambda data: _heater_attributes(data.nozzle_heater_state),
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
        attributes_fn=lambda data: _heater_attributes(data.bed_heater_state),
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
        key="fan_target",
        translation_key="fan_target",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.fan_target,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="speed_factor",
        translation_key="speed_factor",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.speed_factor,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="extrusion_factor",
        translation_key="extrusion_factor",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        value_fn=lambda data: data.extrusion_factor,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="mcu_temperature",
        translation_key="mcu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.mcu_temperature,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="input_voltage",
        translation_key="input_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: data.input_voltage,
    ),
    RepRapFirmwareSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        value_fn=lambda data: data.uptime,
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

    @property
    def extra_state_attributes(self) -> dict[str, StateType] | None:
        """Return optional structured attributes for the sensor."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
