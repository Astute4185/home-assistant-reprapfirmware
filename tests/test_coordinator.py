"""Tests for RepRapFirmware coordinator-derived job metrics."""

from __future__ import annotations

from dataclasses import replace

from custom_components.reprapfirmware.coordinator import RepRapFirmwareCoordinator
from custom_components.reprapfirmware.model import (
    RepRapFirmwareData,
    parse_printer_data,
)


def _make_tracking_coordinator() -> RepRapFirmwareCoordinator:
    """Create a coordinator shell for testing the pure tracking helper."""
    coordinator = object.__new__(RepRapFirmwareCoordinator)
    coordinator._tracked_job_name = None
    coordinator._tracked_layer = None
    coordinator._layer_start_extrusion = None
    coordinator._last_layer_time = None
    coordinator._observed_layer_time = None
    coordinator._last_job_duration = None
    return coordinator


def _job_data(
    *,
    layer: int = 7,
    layer_time: float = 14,
    filament_used: float = 100,
    duration: float = 120,
    job_name: str = "cube.gcode",
    status: str = "processing",
) -> RepRapFirmwareData:
    """Build normalized data for one active-print poll."""
    return parse_printer_data(
        state={"status": status},
        job={
            "duration": duration,
            "layer": layer,
            "layerTime": layer_time,
            "rawExtrusion": filament_used,
            "file": {"fileName": job_name},
        },
        heat={},
        tools=[],
        move={},
        fans=[],
        board={},
    )


def test_job_tracking_calculates_current_layer_filament() -> None:
    """Current-layer filament is measured from the first poll of that layer."""
    coordinator = _make_tracking_coordinator()

    first = coordinator._apply_job_tracking(_job_data())
    same_layer = coordinator._apply_job_tracking(
        _job_data(layer_time=30, filament_used=112.5, duration=136)
    )

    assert first.layer_filament_used == 0.0
    assert first.last_layer_time is None
    assert same_layer.layer_filament_used == 12.5
    assert same_layer.last_layer_time is None


def test_job_tracking_records_previous_layer_time_on_layer_change() -> None:
    """The most recently observed layer time becomes the last-layer value."""
    coordinator = _make_tracking_coordinator()

    coordinator._apply_job_tracking(_job_data())
    coordinator._apply_job_tracking(
        _job_data(layer_time=67, filament_used=112.5, duration=173)
    )
    next_layer = coordinator._apply_job_tracking(
        _job_data(layer=8, layer_time=3, filament_used=115, duration=176)
    )
    next_layer_progress = coordinator._apply_job_tracking(
        _job_data(layer=8, layer_time=20, filament_used=124.5, duration=193)
    )

    assert next_layer.last_layer_time == 67
    assert next_layer.layer_filament_used == 0.0
    assert next_layer_progress.last_layer_time == 67
    assert next_layer_progress.layer_filament_used == 9.5


def test_job_tracking_resets_when_print_stops() -> None:
    """Tracked layer values do not leak into idle printer state."""
    coordinator = _make_tracking_coordinator()

    coordinator._apply_job_tracking(_job_data())
    tracked = coordinator._apply_job_tracking(
        _job_data(layer_time=30, filament_used=112.5, duration=136)
    )
    idle = coordinator._apply_job_tracking(replace(tracked, status="idle"))

    assert tracked.layer_filament_used == 12.5
    assert idle.last_layer_time is None
    assert idle.layer_filament_used is None
    assert coordinator._tracked_job_name is None
    assert coordinator._tracked_layer is None


def test_job_tracking_detects_same_filename_restarted_job() -> None:
    """A duration rewind resets tracking even when the file name is unchanged."""
    coordinator = _make_tracking_coordinator()

    coordinator._apply_job_tracking(_job_data(duration=300))
    coordinator._apply_job_tracking(
        _job_data(layer_time=50, filament_used=125, duration=350)
    )
    restarted = coordinator._apply_job_tracking(
        _job_data(layer=1, layer_time=2, filament_used=1.5, duration=5)
    )

    assert restarted.last_layer_time is None
    assert restarted.layer_filament_used == 0.0
    assert coordinator._tracked_layer == 1
