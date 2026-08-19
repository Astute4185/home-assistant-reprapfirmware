"""RepRapFirmware Object Model parsing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RepRapFirmwareData:
    """Normalized printer data consumed by Home Assistant entities."""

    status: str | None
    current_tool: int | None
    job_name: str | None
    progress: float | None
    print_duration: float | None
    estimated_remaining: float | None
    layer: int | None
    file_size: int | None
    nozzle_temperature: float | None
    nozzle_target: float | None
    bed_temperature: float | None
    bed_target: float | None
    board_name: str | None
    firmware_version: str | None
    board_unique_id: str | None


def parse_printer_data(
    *,
    state: Any,
    job: Any,
    heat: Any,
    tools: Any,
    board: Any,
) -> RepRapFirmwareData:
    """Normalize selected RepRapFirmware Object Model branches."""
    state_obj = _as_dict(state)
    job_obj = _as_dict(job)
    heat_obj = _as_dict(heat)
    tools_list = _as_list(tools)
    board_obj = _as_dict(board)

    current_tool = _as_int(state_obj.get("currentTool"))
    selected_tool = _select_tool(tools_list, current_tool)

    nozzle_index = _first_non_negative_int(selected_tool.get("heaters"))
    bed_index = _first_bed_heater(heat_obj)
    heaters = _as_list(heat_obj.get("heaters"))

    nozzle = _heater_at(heaters, nozzle_index)
    bed = _heater_at(heaters, bed_index)

    file_obj = _as_dict(job_obj.get("file"))
    file_size = _as_int(file_obj.get("size"))
    file_position = _as_int(job_obj.get("filePosition"))

    return RepRapFirmwareData(
        status=_as_str(state_obj.get("status")),
        current_tool=current_tool,
        job_name=_as_str(file_obj.get("fileName")),
        progress=_calculate_progress(file_position, file_size),
        print_duration=_as_float(job_obj.get("duration")),
        estimated_remaining=_estimated_remaining(job_obj),
        layer=_as_int(job_obj.get("layer")),
        file_size=file_size,
        nozzle_temperature=_as_float(nozzle.get("current")),
        nozzle_target=_heater_target(nozzle),
        bed_temperature=_as_float(bed.get("current")),
        bed_target=_heater_target(bed),
        board_name=_board_name(board_obj),
        firmware_version=_as_str(board_obj.get("firmwareVersion")),
        board_unique_id=_as_str(board_obj.get("uniqueId")),
    )


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _select_tool(tools: list[Any], current_tool: int | None) -> dict[str, Any]:
    """Select the current configured tool, falling back to the first tool."""
    parsed = [_as_dict(tool) for tool in tools if isinstance(tool, dict)]
    if not parsed:
        return {}

    if current_tool is not None and current_tool >= 0:
        for tool in parsed:
            if _as_int(tool.get("number")) == current_tool:
                return tool

    return parsed[0]


def _first_non_negative_int(value: Any) -> int | None:
    for item in _as_list(value):
        integer = _as_int(item)
        if integer is not None and integer >= 0:
            return integer
    return None


def _first_bed_heater(heat: dict[str, Any]) -> int | None:
    """Return the first configured bed heater using current then legacy mapping."""
    mapping = _as_list(heat.get("bedHeaterMapping"))
    for group in mapping:
        heater = _first_non_negative_int(group)
        if heater is not None:
            return heater

    return _first_non_negative_int(heat.get("bedHeaters"))


def _heater_at(heaters: list[Any], index: int | None) -> dict[str, Any]:
    if index is None or index < 0 or index >= len(heaters):
        return {}
    return _as_dict(heaters[index])


def _heater_target(heater: dict[str, Any]) -> float | None:
    """Return the target that corresponds to the heater's current state."""
    state = _as_str(heater.get("state"))
    if state in {"off", "offline"}:
        return 0.0
    if state == "standby":
        return _as_float(heater.get("standby"))
    return _as_float(heater.get("active"))


def _calculate_progress(position: int | None, size: int | None) -> float | None:
    if position is None or size is None or size <= 0:
        return None
    progress = (position / size) * 100.0
    return round(min(max(progress, 0.0), 100.0), 1)


def _estimated_remaining(job: dict[str, Any]) -> float | None:
    """Return the best available RRF time-left estimate."""
    times_left = _as_dict(job.get("timesLeft"))
    for key in ("slicer", "file", "filament"):
        value = _as_float(times_left.get(key))
        if value is not None and value >= 0:
            return value
    return None


def _board_name(board: dict[str, Any]) -> str | None:
    return (
        _as_str(board.get("name"))
        or _as_str(board.get("shortName"))
        or _as_str(board.get("boardName"))
    )
