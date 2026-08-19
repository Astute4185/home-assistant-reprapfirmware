"""Tests for RepRapFirmware Object Model normalization."""

from custom_components.reprapfirmware.model import parse_printer_data


def test_parse_active_print_data() -> None:
    """P1 values are normalized from documented RRF Object Model branches."""
    data = parse_printer_data(
        state={"status": "processing", "currentTool": 0},
        job={
            "duration": 120.5,
            "filePosition": 250,
            "layer": 7,
            "timesLeft": {"slicer": 3600, "file": 3700, "filament": 3800},
            "file": {"fileName": "cube.gcode", "size": 1000},
        },
        heat={
            "bedHeaterMapping": [[0]],
            "heaters": [
                {"current": 59.5, "active": 60, "standby": 0, "state": "active"},
                {"current": 209.7, "active": 210, "standby": 160, "state": "active"},
            ],
        },
        tools=[{"number": 0, "heaters": [1]}],
        board={
            "name": "Duet 3 Mini 5+ WiFi",
            "firmwareVersion": "3.6.0",
            "uniqueId": "ABC123",
        },
    )

    assert data.status == "processing"
    assert data.current_tool == 0
    assert data.job_name == "cube.gcode"
    assert data.progress == 25.0
    assert data.print_duration == 120.5
    assert data.estimated_remaining == 3600.0
    assert data.layer == 7
    assert data.file_size == 1000
    assert data.nozzle_temperature == 209.7
    assert data.nozzle_target == 210.0
    assert data.bed_temperature == 59.5
    assert data.bed_target == 60.0
    assert data.board_name == "Duet 3 Mini 5+ WiFi"
    assert data.firmware_version == "3.6.0"
    assert data.board_unique_id == "ABC123"


def test_parse_uses_selected_tool_and_standby_target() -> None:
    """The current tool controls nozzle mapping and standby uses standby target."""
    data = parse_printer_data(
        state={"status": "paused", "currentTool": 1},
        job={"file": {}},
        heat={
            "bedHeaters": [0],
            "heaters": [
                {"current": 30, "active": 60, "standby": 0, "state": "off"},
                {"current": 25, "active": 200, "standby": 150, "state": "off"},
                {"current": 145, "active": 220, "standby": 145, "state": "standby"},
            ],
        },
        tools=[
            {"number": 0, "heaters": [1]},
            {"number": 1, "heaters": [2]},
        ],
        board={"shortName": "Mini5+"},
    )

    assert data.nozzle_temperature == 145.0
    assert data.nozzle_target == 145.0
    assert data.bed_target == 0.0
    assert data.board_name == "Mini5+"


def test_parse_handles_missing_optional_data() -> None:
    """Missing RRF values result in None instead of entity exceptions."""
    data = parse_printer_data(
        state={"status": "idle", "currentTool": -1},
        job={},
        heat={},
        tools=[],
        board={},
    )

    assert data.status == "idle"
    assert data.progress is None
    assert data.job_name is None
    assert data.nozzle_temperature is None
    assert data.bed_temperature is None
    assert data.firmware_version is None


def test_progress_is_clamped_and_invalid_size_is_ignored() -> None:
    """Malformed or transitional file positions cannot create invalid percentages."""
    overrun = parse_printer_data(
        state={},
        job={"filePosition": 1100, "file": {"size": 1000}},
        heat={},
        tools=[],
        board={},
    )
    no_size = parse_printer_data(
        state={},
        job={"filePosition": 10, "file": {"size": 0}},
        heat={},
        tools=[],
        board={},
    )

    assert overrun.progress == 100.0
    assert no_size.progress is None
