"""Printer transition and fault detection for RepRapFirmware."""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    EVENT_CONNECTION_LOST_DURING_PRINT,
    EVENT_PRINT_COMPLETED,
    EVENT_PRINT_PAUSED,
    EVENT_PRINTER_FAULT,
    EVENT_PRINTER_HALTED,
)
from .model import RepRapFirmwareData


@dataclass(frozen=True, slots=True)
class RepRapFirmwareEvent:
    """One normalized printer event exposed to Home Assistant."""

    event_type: str
    previous_status: str | None
    current_status: str | None
    job_name: str | None = None
    print_duration: float | None = None
    progress: float | None = None
    fault_type: str | None = None
    fault_source: str | None = None
    fault_reason: str | None = None

    def as_event_data(self) -> dict[str, str | float]:
        """Return non-empty event data suitable for an EventEntity."""
        data: dict[str, str | float] = {}
        if self.previous_status is not None:
            data["previous_status"] = self.previous_status
        if self.current_status is not None:
            data["current_status"] = self.current_status
        if self.job_name is not None:
            data["job_name"] = self.job_name
        if self.print_duration is not None:
            data["print_duration"] = self.print_duration
        if self.progress is not None:
            data["progress"] = self.progress
        if self.fault_type is not None:
            data["fault_type"] = self.fault_type
        if self.fault_source is not None:
            data["fault_source"] = self.fault_source
        if self.fault_reason is not None:
            data["fault_reason"] = self.fault_reason
        return data


class RepRapFirmwareEventTracker:
    """Track coordinator updates and emit one-shot printer transitions."""

    def __init__(
        self,
        initial_data: RepRapFirmwareData | None,
        *,
        initial_online: bool,
    ) -> None:
        """Initialize transition history without emitting startup events."""
        self._previous_data = initial_data if initial_online else None
        self._was_online = initial_online
        self._continuity_lost = not initial_online

    def process(
        self,
        current_data: RepRapFirmwareData | None,
        *,
        is_online: bool,
    ) -> tuple[RepRapFirmwareEvent, ...]:
        """Return events caused by the latest coordinator result."""
        previous = self._previous_data
        events: list[RepRapFirmwareEvent] = []

        if not is_online:
            if (
                self._was_online
                and previous is not None
                and previous.status == "processing"
            ):
                events.append(
                    RepRapFirmwareEvent(
                        event_type=EVENT_CONNECTION_LOST_DURING_PRINT,
                        previous_status=previous.status,
                        current_status=None,
                        job_name=previous.job_name,
                        print_duration=previous.print_duration,
                        progress=previous.progress,
                    )
                )
                self._continuity_lost = True
            self._was_online = False
            return tuple(events)

        if current_data is None:
            self._was_online = True
            return ()

        if previous is not None:
            previous_status = previous.status
            current_status = current_data.status
            context = _best_job_context(current_data, previous)

            detailed_faults = _detect_faults(previous, current_data, context)
            events.extend(detailed_faults)

            if current_status == "halted" and previous_status != "halted":
                # Preserve the original lifecycle event for compatibility.
                events.append(
                    RepRapFirmwareEvent(
                        event_type=EVENT_PRINTER_HALTED,
                        previous_status=previous_status,
                        current_status=current_status,
                        job_name=context.job_name,
                        print_duration=context.print_duration,
                        progress=context.progress,
                    )
                )

                # If RRF did not expose a more specific heater/filament cause,
                # still provide the canonical fault event required by the
                # notification contract.
                if not detailed_faults:
                    events.append(
                        _fault_event(
                            previous,
                            current_data,
                            context,
                            fault_type="machine",
                            fault_source="printer",
                            fault_reason="halted",
                        )
                    )

            # A connectivity gap makes completion/pause inference ambiguous. The
            # first successful update after recovery re-establishes the baseline.
            if not self._continuity_lost:
                if previous_status == "processing" and current_status == "idle":
                    events.append(
                        RepRapFirmwareEvent(
                            event_type=EVENT_PRINT_COMPLETED,
                            previous_status=previous_status,
                            current_status=current_status,
                            job_name=previous.job_name,
                            print_duration=previous.print_duration,
                            progress=previous.progress,
                        )
                    )
                elif previous_status == "processing" and current_status == "paused":
                    events.append(
                        RepRapFirmwareEvent(
                            event_type=EVENT_PRINT_PAUSED,
                            previous_status=previous_status,
                            current_status=current_status,
                            job_name=context.job_name,
                            print_duration=context.print_duration,
                            progress=context.progress,
                        )
                    )

        self._previous_data = current_data
        self._was_online = True
        self._continuity_lost = False
        return tuple(events)


def _detect_faults(
    previous: RepRapFirmwareData,
    current: RepRapFirmwareData,
    context: RepRapFirmwareData,
) -> list[RepRapFirmwareEvent]:
    """Detect new heater and filament faults without repeating each poll."""
    events: list[RepRapFirmwareEvent] = []

    heater_states = (
        (
            "nozzle",
            previous.nozzle_heater_state,
            current.nozzle_heater_state,
        ),
        (
            "bed",
            previous.bed_heater_state,
            current.bed_heater_state,
        ),
    )
    for source, previous_state, current_state in heater_states:
        if _is_heater_fault(current_state) and not _is_heater_fault(previous_state):
            events.append(
                _fault_event(
                    previous,
                    current,
                    context,
                    fault_type="heater",
                    fault_source=source,
                    fault_reason=current_state or "fault",
                )
            )

    previous_filament = previous.filament_monitor_status
    current_filament = current.filament_monitor_status
    if _is_filament_fault(current_filament) and (
        not _is_filament_fault(previous_filament)
        or _normalized(previous_filament) != _normalized(current_filament)
    ):
        events.append(
            _fault_event(
                previous,
                current,
                context,
                fault_type="filament",
                fault_source="filament_monitor",
                fault_reason=current_filament or "unknown",
            )
        )

    return events


def _fault_event(
    previous: RepRapFirmwareData,
    current: RepRapFirmwareData,
    context: RepRapFirmwareData,
    *,
    fault_type: str,
    fault_source: str,
    fault_reason: str,
) -> RepRapFirmwareEvent:
    """Build the canonical printer fault event."""
    return RepRapFirmwareEvent(
        event_type=EVENT_PRINTER_FAULT,
        previous_status=previous.status,
        current_status=current.status,
        job_name=context.job_name,
        print_duration=context.print_duration,
        progress=context.progress,
        fault_type=fault_type,
        fault_source=fault_source,
        fault_reason=fault_reason,
    )


def _is_heater_fault(state: str | None) -> bool:
    """Return whether an RRF heater state is faulted."""
    return _normalized(state) == "fault"


def _is_filament_fault(status: str | None) -> bool:
    """Mirror the filament-monitor binary-sensor problem semantics."""
    normalized = _normalized(status)
    return normalized is not None and normalized != "ok"


def _normalized(value: str | None) -> str | None:
    """Normalize an RRF status for comparisons without altering event data."""
    if value is None:
        return None
    return value.casefold()


def _best_job_context(
    current: RepRapFirmwareData,
    previous: RepRapFirmwareData,
) -> RepRapFirmwareData:
    """Prefer current job context unless RRF cleared it during a transition."""
    if current.job_name is not None:
        return current
    return previous
