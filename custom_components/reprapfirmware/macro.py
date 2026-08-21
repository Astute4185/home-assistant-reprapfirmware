"""RepRapFirmware macro discovery and execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1

from .api import RepRapFirmwareFileItem
from .const import MACRO_DIRECTORY


def _safe_top_level_name(value: str) -> str | None:
    """Return a normalized safe top-level filename, or None if unsafe."""
    name = value.strip()
    if (
        not name
        or "/" in name
        or "\\" in name
        or '"' in name
        or "\n" in name
        or "\r" in name
    ):
        return None
    return name


def _macro_name_aliases(value: str) -> frozenset[str]:
    """Return case-insensitive aliases for extensionless and .g macro names."""
    normalized = value.strip().casefold()
    if not normalized:
        return frozenset()

    aliases = {normalized}
    if normalized.endswith(".g"):
        aliases.add(normalized[:-2])
    else:
        aliases.add(f"{normalized}.g")
    return frozenset(aliases)


@dataclass(frozen=True, slots=True)
class RepRapFirmwareMacro:
    """One top-level RepRapFirmware macro exposed to Home Assistant."""

    name: str
    path: str

    @property
    def display_name(self) -> str:
        """Return a friendly macro label while preserving extensionless names."""
        return self.name[:-2] if self.name.casefold().endswith(".g") else self.name

    @property
    def entity_key(self) -> str:
        """Return a stable entity unique-id suffix for this macro path."""
        digest = sha1(self.path.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
        return f"macro_{digest}"

    @property
    def gcode(self) -> str:
        """Return the RRF command used to execute the macro."""
        return f'M98 P"{self.path}"'

    def exact_matches(self, value: str) -> bool:
        """Return whether a user value exactly identifies this macro."""
        requested = value.strip()
        if requested.startswith(MACRO_DIRECTORY):
            requested = requested[len(MACRO_DIRECTORY) :]

        safe_name = _safe_top_level_name(requested)
        return safe_name is not None and safe_name.casefold() == self.name.casefold()

    def matches(self, value: str) -> bool:
        """Return whether a user value identifies this macro by exact name or alias.

        Duet user macros may be created with or without a ``.g`` extension. For
        convenience, either spelling is accepted when it unambiguously refers to
        the same discovered top-level macro.
        """
        requested = value.strip()
        if requested.startswith(MACRO_DIRECTORY):
            requested = requested[len(MACRO_DIRECTORY) :]

        safe_name = _safe_top_level_name(requested)
        if safe_name is None:
            return False

        return bool(_macro_name_aliases(safe_name) & _macro_name_aliases(self.name))


def discover_macros(
    items: tuple[RepRapFirmwareFileItem, ...],
) -> tuple[RepRapFirmwareMacro, ...]:
    """Convert a top-level rr_filelist response into safe macro definitions.

    RepRapFirmware/Duet macros in ``/macros`` are regular G-code text files and
    do not require a ``.g`` extension. Discovery therefore exposes every safe
    top-level regular file and ignores only directories or unsafe/nested names.
    """
    macros: list[RepRapFirmwareMacro] = []
    for item in items:
        if item.item_type != "f":
            continue

        name = _safe_top_level_name(item.name)
        if name is None:
            continue

        macros.append(
            RepRapFirmwareMacro(
                name=name,
                path=f"{MACRO_DIRECTORY}{name}",
            )
        )

    return tuple(sorted(macros, key=lambda macro: macro.name.casefold()))
