"""Tests for state-aware RepRapFirmware machine controls."""

from custom_components.reprapfirmware.control import CONTROL_COMMANDS_BY_KEY


def test_control_gcode_matches_p2_contract() -> None:
    """P2 controls must send the documented RepRapFirmware commands."""
    assert CONTROL_COMMANDS_BY_KEY["home"].gcode == "G28"
    assert CONTROL_COMMANDS_BY_KEY["pause"].gcode == "M25"
    assert CONTROL_COMMANDS_BY_KEY["resume"].gcode == "M24"
    assert CONTROL_COMMANDS_BY_KEY["cancel"].gcode == "M0"


def test_home_is_only_available_when_idle() -> None:
    """Home is blocked while a job is active, paused, or halted."""
    command = CONTROL_COMMANDS_BY_KEY["home"]
    assert command.is_allowed("idle")
    assert not command.is_allowed("processing")
    assert not command.is_allowed("paused")
    assert not command.is_allowed("halted")


def test_pause_is_only_available_while_processing() -> None:
    """Pause is only valid for an active print."""
    command = CONTROL_COMMANDS_BY_KEY["pause"]
    assert command.is_allowed("processing")
    assert not command.is_allowed("idle")
    assert not command.is_allowed("paused")


def test_resume_is_only_available_while_paused() -> None:
    """Resume is only valid for a paused print."""
    command = CONTROL_COMMANDS_BY_KEY["resume"]
    assert command.is_allowed("paused")
    assert not command.is_allowed("idle")
    assert not command.is_allowed("processing")


def test_cancel_is_available_while_processing_or_paused() -> None:
    """Cancel is available for active and paused jobs only."""
    command = CONTROL_COMMANDS_BY_KEY["cancel"]
    assert command.is_allowed("processing")
    assert command.is_allowed("paused")
    assert not command.is_allowed("idle")
    assert not command.is_allowed("halted")


def test_unknown_state_disables_every_control() -> None:
    """No machine command is exposed when printer state is unknown."""
    assert all(
        not command.is_allowed(None) for command in CONTROL_COMMANDS_BY_KEY.values()
    )
