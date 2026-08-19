"""Machine-control definitions for RepRapFirmware."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RepRapFirmwareControlCommand:
    """Describe a state-aware printer command."""

    key: str
    gcode: str
    allowed_states: frozenset[str]

    def is_allowed(self, state: str | None) -> bool:
        """Return whether the command is allowed for the current machine state."""
        return state in self.allowed_states


CONTROL_COMMANDS: tuple[RepRapFirmwareControlCommand, ...] = (
    RepRapFirmwareControlCommand(
        key="home",
        gcode="G28",
        allowed_states=frozenset({"idle"}),
    ),
    RepRapFirmwareControlCommand(
        key="pause",
        gcode="M25",
        allowed_states=frozenset({"processing"}),
    ),
    RepRapFirmwareControlCommand(
        key="resume",
        gcode="M24",
        allowed_states=frozenset({"paused"}),
    ),
    RepRapFirmwareControlCommand(
        key="cancel",
        gcode="M0",
        allowed_states=frozenset({"processing", "paused"}),
    ),
)

CONTROL_COMMANDS_BY_KEY = {command.key: command for command in CONTROL_COMMANDS}
