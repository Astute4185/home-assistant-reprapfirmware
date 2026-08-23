"""Tests for RepRapFirmware Object Model normalization."""

from custom_components.reprapfirmware.model import parse_printer_data


def test_parse_active_print_data() -> None:
    """Printer values are normalized from documented RRF Object Model branches."""
    data = parse_printer_data(
        state={
            "status": "processing",
            "currentTool": 0,
            "upTime": 12345,
        },
        job={
            "duration": 120.5,
            "filePosition": 250,
            "layer": 7,
            "rawExtrusion": 456.7,
            "timesLeft": {"slicer": 3600, "file": 3700, "filament": 3800},
            "file": {"fileName": "cube.gcode", "size": 1000},
        },
        heat={
            "bedHeaterMapping": [[0]],
            "heaters": [
                {"current": 59.5, "active": 60, "standby": 0, "state": "active"},
                {
                    "current": 209.7,
                    "active": 210,
                    "standby": 160,
                    "state": "active",
                },
            ],
        },
        tools=[
            {
                "number": 0,
                "heaters": [1],
                "fans": [1],
                "extruders": [0],
                "active": [210],
                "standby": [160],
                "state": "active",
            }
        ],
        move={
            "axes": [
                {"letter": "X", "userPosition": 12.5, "homed": True},
                {"letter": "Y", "userPosition": -3.25, "homed": True},
                {"letter": "Z", "userPosition": 101.234, "homed": False},
            ],
            "extruders": [{"factor": 0.95}],
            "speedFactor": 0.85,
        },
        fans=[
            {"actualValue": 0.2, "requestedValue": 0.25},
            {"actualValue": 0.75, "requestedValue": 0.8},
        ],
        filament_monitors=[{"status": "ok", "type": "simple"}],
        board={
            "name": "Duet 3 Mini 5+ WiFi",
            "firmwareVersion": "3.6.0",
            "uniqueId": "ABC123",
            "mcuTemp": {"current": 46.25, "min": 30, "max": 52},
            "vIn": {"current": 23.87, "min": 23.5, "max": 24.2},
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
    assert data.filament_used == 456.7
    assert data.nozzle_temperature == 209.7
    assert data.nozzle_target == 210.0
    assert data.nozzle_heater_state == "active"
    assert data.bed_temperature == 59.5
    assert data.bed_target == 60.0
    assert data.bed_heater_state == "active"
    assert data.x_position == 12.5
    assert data.y_position == -3.25
    assert data.z_position == 101.234
    assert data.x_homed is True
    assert data.y_homed is True
    assert data.z_homed is False
    assert data.fan_speed == 75.0
    assert data.fan_target == 80.0
    assert data.speed_factor == 85.0
    assert data.extrusion_factor == 95.0
    assert data.filament_monitor_status == "ok"
    assert data.mcu_temperature == 46.25
    assert data.input_voltage == 23.87
    assert data.uptime == 12345.0
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
            {"number": 0, "heaters": [1], "extruders": [0]},
            {"number": 1, "heaters": [2], "extruders": [1]},
        ],
        move={"extruders": [{"factor": 1.0}, {"factor": 1.1}]},
        fans=[],
        board={"shortName": "Mini5+"},
    )

    assert data.nozzle_temperature == 145.0
    assert data.nozzle_target == 145.0
    assert data.nozzle_heater_state == "standby"
    assert data.bed_target is None
    assert data.bed_heater_state == "off"
    assert data.extrusion_factor == 110.0
    assert data.board_name == "Mini5+"


def test_parse_falls_back_to_tool_and_fileinfo_metadata() -> None:
    """Tool/fileinfo data fills fields omitted by standard Object Model replies."""
    data = parse_printer_data(
        state={"status": "processing", "currentTool": 0},
        job={
            "filePosition": 500,
            "file": {"fileName": "cube.gcode"},
        },
        heat={
            "bedHeaters": [0],
            "heaters": [
                {"current": 55, "active": 60, "state": "active"},
                {"current": 195, "state": "active"},
            ],
        },
        tools=[
            {
                "number": 0,
                "heaters": [1],
                "active": [205],
                "standby": [150],
                "state": "active",
            }
        ],
        move={},
        fans=[],
        board={},
        file_info={"fileName": "/gcodes/cube.gcode", "size": 2000},
    )

    assert data.file_size == 2000
    assert data.progress == 25.0
    assert data.nozzle_target == 205.0
    assert data.bed_target == 60.0


def test_zero_heater_targets_are_treated_as_unset() -> None:
    """Zero-degree heater targets should not create graphable setpoints."""
    data = parse_printer_data(
        state={"status": "idle", "currentTool": 0},
        job={"file": {}},
        heat={
            "bedHeaters": [0],
            "heaters": [
                {"current": 24, "active": 0, "standby": 0, "state": "off"},
                {"current": 25, "active": 0, "standby": 0, "state": "active"},
            ],
        },
        tools=[
            {
                "number": 0,
                "heaters": [1],
                "active": [0],
                "standby": [0],
                "state": "active",
            }
        ],
        move={},
        fans=[],
        board={},
    )

    assert data.nozzle_target is None
    assert data.bed_target is None


def test_parse_fan_falls_back_to_first_configured_fan() -> None:
    """A machine without a tool fan mapping still exposes useful fan values."""
    data = parse_printer_data(
        state={"currentTool": -1},
        job={},
        heat={},
        tools=[],
        move={"speedFactor": 1.25, "extruders": [{"factor": 1.05}]},
        fans=[{"actualValue": -1, "requestedValue": 0.4}],
        board={},
    )

    assert data.fan_speed == 40.0
    assert data.fan_target == 40.0
    assert data.speed_factor == 125.0
    assert data.extrusion_factor == 105.0


def test_parse_filament_monitor_fault_status() -> None:
    """The first configured filament monitor exposes its RRF status."""
    data = parse_printer_data(
        state={},
        job={},
        heat={},
        tools=[],
        move={},
        fans=[],
        filament_monitors=[{"status": "noFilament"}],
        board={},
    )

    assert data.filament_monitor_status == "noFilament"


def test_parse_handles_missing_optional_data() -> None:
    """Missing RRF values result in None instead of entity exceptions."""
    data = parse_printer_data(
        state={"status": "idle", "currentTool": -1},
        job={},
        heat={},
        tools=[],
        move={},
        fans=[],
        board={},
    )

    assert data.status == "idle"
    assert data.progress is None
    assert data.job_name is None
    assert data.filament_used is None
    assert data.nozzle_temperature is None
    assert data.nozzle_heater_state is None
    assert data.bed_temperature is None
    assert data.bed_heater_state is None
    assert data.x_position is None
    assert data.x_homed is None
    assert data.fan_speed is None
    assert data.fan_target is None
    assert data.speed_factor is None
    assert data.extrusion_factor is None
    assert data.filament_monitor_status is None
    assert data.mcu_temperature is None
    assert data.input_voltage is None
    assert data.uptime is None
    assert data.firmware_version is None


def test_progress_is_clamped_and_invalid_size_is_ignored() -> None:
    """Malformed or transitional file positions cannot create invalid percentages."""
    overrun = parse_printer_data(
        state={},
        job={"filePosition": 1100, "file": {"size": 1000}},
        heat={},
        tools=[],
        move={},
        fans=[],
        board={},
    )
    no_size = parse_printer_data(
        state={},
        job={"filePosition": 10, "file": {"size": 0}},
        heat={},
        tools=[],
        move={},
        fans=[],
        board={},
    )

    assert overrun.progress == 100.0
    assert no_size.progress is None
