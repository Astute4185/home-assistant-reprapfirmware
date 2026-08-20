"""Printer transition detection for RepRapFirmware."""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    EVENT_CONNECTION_LOST_DURING_PRINT,
    EVENT_PRINT_COMPLETED,
    EVENT_PRINT_PAUSED,
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

            if current_status == "halted" and previous_status != "halted":
                context = _best_job_context(current_data, previous)
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
                elif (
                    previous_status == "processing" and current_status == "paused"
                ):
                    context = _best_job_context(current_data, previous)
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


def _best_job_context(
    current: RepRapFirmwareData,
    previous: RepRapFirmwareData,
) -> RepRapFirmwareData:
    """Prefer current job context unless RRF cleared it during a transition."""
    if current.job_name is not None:
        return current
    return previous
