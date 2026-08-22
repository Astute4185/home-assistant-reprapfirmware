"""Tests for P4 printer transition detection."""

from dataclasses import replace

from custom_components.reprapfirmware.const import (
    EVENT_CONNECTION_LOST_DURING_PRINT,
    EVENT_PRINT_COMPLETED,
    EVENT_PRINT_PAUSED,
    EVENT_PRINTER_FAULT,
    EVENT_PRINTER_HALTED,
)
from custom_components.reprapfirmware.events import RepRapFirmwareEventTracker
from custom_components.reprapfirmware.model import RepRapFirmwareData


def _data(
    status: str,
    *,
    job_name: str | None = "part.gcode",
    duration: float | None = 120.0,
    progress: float | None = 50.0,
) -> RepRapFirmwareData:
    return RepRapFirmwareData(
        status=status,
        current_tool=0,
        job_name=job_name,
        progress=progress,
        print_duration=duration,
        estimated_remaining=60.0,
        layer=3,
        file_size=1000,
        filament_used=250.0,
        nozzle_temperature=200.0,
        nozzle_target=200.0,
        nozzle_heater_state="active",
        bed_temperature=60.0,
        bed_target=60.0,
        bed_heater_state="active",
        x_position=0.0,
        y_position=0.0,
        z_position=0.0,
        x_homed=True,
        y_homed=True,
        z_homed=True,
        fan_speed=50.0,
        fan_target=50.0,
        speed_factor=100.0,
        extrusion_factor=100.0,
        filament_monitor_status=None,
        mcu_temperature=45.0,
        input_voltage=24.0,
        uptime=3600.0,
        board_name="Duet",
        firmware_version="3.6.0",
        board_unique_id="ABC",
    )


def test_processing_to_idle_emits_completion_with_previous_job_context() -> None:
    """Completion retains job values that RRF may clear once it becomes idle."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)

    (event,) = tracker.process(
        _data("idle", job_name=None, duration=None, progress=None),
        is_online=True,
    )

    assert event.event_type == EVENT_PRINT_COMPLETED
    assert event.job_name == "part.gcode"
    assert event.print_duration == 120.0
    assert event.previous_status == "processing"
    assert event.current_status == "idle"


def test_processing_to_paused_emits_pause() -> None:
    """A direct processing-to-paused transition emits the pause signal."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)

    (event,) = tracker.process(
        replace(_data("paused"), print_duration=135.0),
        is_online=True,
    )

    assert event.event_type == EVENT_PRINT_PAUSED
    assert event.print_duration == 135.0


def test_entering_halted_emits_lifecycle_and_canonical_fault_events() -> None:
    """An unexplained halt remains compatible and also raises printer_fault."""
    tracker = RepRapFirmwareEventTracker(_data("idle"), initial_online=True)

    events = tracker.process(_data("halted", job_name=None), is_online=True)

    assert [event.event_type for event in events] == [
        EVENT_PRINTER_HALTED,
        EVENT_PRINTER_FAULT,
    ]
    fault = events[1]
    assert fault.fault_type == "machine"
    assert fault.fault_source == "printer"
    assert fault.fault_reason == "halted"


def test_first_offline_update_during_processing_emits_once() -> None:
    """Connection loss during processing is edge-triggered, not repeated."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)

    first = tracker.process(_data("processing"), is_online=False)
    second = tracker.process(_data("processing"), is_online=False)

    assert [event.event_type for event in first] == [EVENT_CONNECTION_LOST_DURING_PRINT]
    assert second == ()


def test_recovery_to_idle_does_not_claim_completion_after_gap() -> None:
    """A connectivity gap prevents an ambiguous completion notification."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)
    tracker.process(_data("processing"), is_online=False)

    assert tracker.process(_data("idle", job_name=None), is_online=True) == ()


def test_successful_recovery_reestablishes_transition_baseline() -> None:
    """Normal completion detection resumes after a successful recovery sample."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)
    tracker.process(_data("processing"), is_online=False)
    tracker.process(_data("processing"), is_online=True)

    (event,) = tracker.process(_data("idle", job_name=None), is_online=True)

    assert event.event_type == EVENT_PRINT_COMPLETED


def test_non_matching_transitions_emit_nothing() -> None:
    """Idle/busy and duplicate halted states do not create false events."""
    tracker = RepRapFirmwareEventTracker(_data("idle"), initial_online=True)

    assert tracker.process(_data("busy"), is_online=True) == ()
    tracker.process(_data("halted"), is_online=True)
    assert tracker.process(_data("halted"), is_online=True) == ()


def test_nozzle_heater_fault_emits_canonical_fault_once() -> None:
    """A nozzle heater entering RRF fault state emits one fault event."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)
    faulted = replace(_data("processing"), nozzle_heater_state="fault")

    first = tracker.process(faulted, is_online=True)
    second = tracker.process(faulted, is_online=True)

    assert [event.event_type for event in first] == [EVENT_PRINTER_FAULT]
    assert first[0].fault_type == "heater"
    assert first[0].fault_source == "nozzle"
    assert first[0].fault_reason == "fault"
    assert second == ()


def test_bed_heater_fault_emits_canonical_fault() -> None:
    """A bed heater entering RRF fault state identifies the bed source."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)

    (event,) = tracker.process(
        replace(_data("processing"), bed_heater_state="fault"),
        is_online=True,
    )

    assert event.event_type == EVENT_PRINTER_FAULT
    assert event.fault_type == "heater"
    assert event.fault_source == "bed"


def test_filament_fault_emits_raw_rrf_reason_once() -> None:
    """A new filament-monitor problem raises a fault with the raw RRF reason."""
    tracker = RepRapFirmwareEventTracker(
        replace(_data("processing"), filament_monitor_status="ok"),
        initial_online=True,
    )
    faulted = replace(
        _data("processing"),
        filament_monitor_status="noFilament",
    )

    first = tracker.process(faulted, is_online=True)
    second = tracker.process(faulted, is_online=True)

    assert [event.event_type for event in first] == [EVENT_PRINTER_FAULT]
    assert first[0].fault_type == "filament"
    assert first[0].fault_source == "filament_monitor"
    assert first[0].fault_reason == "noFilament"
    assert second == ()


def test_changed_filament_fault_reason_emits_new_fault() -> None:
    """A changed filament fault reason is actionable and emits a fresh event."""
    tracker = RepRapFirmwareEventTracker(
        replace(_data("processing"), filament_monitor_status="noFilament"),
        initial_online=True,
    )

    (event,) = tracker.process(
        replace(_data("processing"), filament_monitor_status="sensorError"),
        is_online=True,
    )

    assert event.event_type == EVENT_PRINTER_FAULT
    assert event.fault_type == "filament"
    assert event.fault_reason == "sensorError"


def test_halted_with_heater_fault_does_not_add_duplicate_generic_fault() -> None:
    """A known heater cause prevents an additional generic halted fault event."""
    tracker = RepRapFirmwareEventTracker(_data("processing"), initial_online=True)

    events = tracker.process(
        replace(
            _data("halted"),
            nozzle_heater_state="fault",
        ),
        is_online=True,
    )

    assert [event.event_type for event in events] == [
        EVENT_PRINTER_FAULT,
        EVENT_PRINTER_HALTED,
    ]
    assert events[0].fault_type == "heater"
    assert events[0].fault_source == "nozzle"
