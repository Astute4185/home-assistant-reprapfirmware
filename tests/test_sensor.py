"""Tests for RepRapFirmware sensor descriptions."""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfLength, UnitOfTime

from custom_components.reprapfirmware.sensor import SENSORS


def test_print_job_metric_sensors_are_registered() -> None:
    """All print-job metrics added for dashboard use are exposed as sensors."""
    sensors = {description.key: description for description in SENSORS}

    duration_keys = {
        "estimated_remaining_filament",
        "estimated_remaining_file",
        "estimated_remaining_slicer",
        "warm_up_duration",
        "layer_time",
        "last_layer_time",
    }
    for key in duration_keys:
        description = sensors[key]
        assert description.device_class is SensorDeviceClass.DURATION
        assert description.native_unit_of_measurement is UnitOfTime.SECONDS

    for key in {"total_filament", "filament_remaining", "layer_filament_used"}:
        assert sensors[key].native_unit_of_measurement is UnitOfLength.MILLIMETERS

    assert "total_layers" in sensors
    assert "layers_remaining" in sensors
