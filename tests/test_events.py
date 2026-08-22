"""Tests for P4 printer transition detection."""

from dataclasses import replace

from custom_components.reprapfirmware.const import (
    EVENT_CONNECTION_LOST_DURING_PRINT,
    EVENT_PRINT_COMPLETED,
    EVENT_PRINT_PAUSED,
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
        nozzle_temperature=200.0,
        nozzle_target=200.0,
        bed_temperature=60.0,
        bed_target=60.0,
        x_position=0.0,
        y_position=0.0,
        z_position=0.0,
        fan_speed=0.0,
        speed_factor=100.0,
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


def test_entering_halted_emits_fault_from_any_prior_state() -> None:
    """Entering halted is reported independently of print activity."""
    tracker = RepRapFirmwareEventTracker(_data("idle"), initial_online=True)

    (event,) = tracker.process(_data("halted", job_name=None), is_online=True)

    assert event.event_type == EVENT_PRINTER_HALTED
    assert event.current_status == "halted"


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
