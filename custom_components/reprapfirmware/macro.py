"""RepRapFirmware macro discovery and execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from .api import RepRapFirmwareFileItem
from .const import MACRO_DIRECTORY


@dataclass(frozen=True, slots=True)
class RepRapFirmwareMacro:
    """One top-level RepRapFirmware macro exposed to Home Assistant."""

    name: str
    path: str

    @property
    def display_name(self) -> str:
        """Return the filename without the .g suffix for entity display."""
        return self.name[:-2]

    @property
    def entity_key(self) -> str:
        """Return a stable entity unique-id suffix for this macro path."""
        digest = sha1(self.path.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
        return f"macro_{digest}"

    @property
    def gcode(self) -> str:
        """Return the RRF command used to execute the macro."""
        return f'M98 P"{self.path}"'


def discover_macros(
    items: tuple[RepRapFirmwareFileItem, ...],
) -> tuple[RepRapFirmwareMacro, ...]:
    """Convert a top-level rr_filelist response into safe .g macro definitions."""
    macros: list[RepRapFirmwareMacro] = []
    for item in items:
        name = item.name
        if (
            item.item_type != "f"
            or not name.strip()
            or not name.lower().endswith(".g")
            or "/" in name
            or "\\" in name
            or '"' in name
            or "\n" in name
            or "\r" in name
        ):
            continue
        macros.append(
            RepRapFirmwareMacro(
                name=name,
                path=f"{MACRO_DIRECTORY}{name}",
            )
        )

    return tuple(sorted(macros, key=lambda macro: macro.name.casefold()))
