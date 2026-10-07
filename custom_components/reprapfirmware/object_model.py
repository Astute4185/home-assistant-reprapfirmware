"""Configurable RepRapFirmware Object Model entity helpers."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_OBJECT_MODEL_ENTITIES,
    ENTITY_TYPE_BINARY_SENSOR,
    ENTITY_TYPE_SENSOR,
    MAX_OBJECT_MODEL_ENTITIES,
)

ObjectModelScalar = bool | int | float | str | None

_PATH_PATTERN = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*(?:(?:\.[A-Za-z_][A-Za-z0-9_]*)|(?:\[\d+\]))*$"
)
_TRUE_STRINGS = frozenset({"1", "true", "on", "yes"})
_FALSE_STRINGS = frozenset({"0", "false", "off", "no"})


@dataclass(frozen=True, slots=True)
class ObjectModelEntityConfig:
    """One user-configured Object Model entity."""

    path: str
    name: str
    entity_type: str
    unit: str | None = None
    invert: bool = False

    @property
    def entity_key(self) -> str:
        """Return a stable entity key based on the configured Object Model path."""
        digest = hashlib.sha256(self.path.encode("utf-8")).hexdigest()[:16]
        return f"object_model_{digest}"

    def as_dict(self) -> dict[str, str | bool]:
        """Serialize the configuration for ConfigEntry.options."""
        data: dict[str, str | bool] = {
            "path": self.path,
            "name": self.name,
            "entity_type": self.entity_type,
        }
        if self.unit is not None:
            data["unit"] = self.unit
        if self.entity_type == ENTITY_TYPE_BINARY_SENSOR and self.invert:
            data["invert"] = True
        return data


def normalize_object_model_path(value: str) -> str:
    """Validate and normalize a RepRapFirmware Object Model key path."""
    path = value.strip()
    if not path or len(path) > 200 or _PATH_PATTERN.fullmatch(path) is None:
        raise ValueError("invalid Object Model path")
    return path


def build_object_model_config(
    *,
    path: str,
    name: str,
    entity_type: str,
    unit: str | None = None,
    invert: bool = False,
) -> ObjectModelEntityConfig:
    """Build and validate one Object Model entity configuration."""
    normalized_path = normalize_object_model_path(path)
    normalized_name = name.strip()
    if not normalized_name or len(normalized_name) > 100:
        raise ValueError("invalid entity name")
    if entity_type not in {ENTITY_TYPE_SENSOR, ENTITY_TYPE_BINARY_SENSOR}:
        raise ValueError("invalid entity type")
    if not isinstance(invert, bool):
        raise ValueError("invalid inversion flag")

    normalized_unit = unit.strip() if isinstance(unit, str) else None
    normalized_unit = normalized_unit or None
    if normalized_unit is not None and len(normalized_unit) > 32:
        raise ValueError("invalid unit")

    if entity_type == ENTITY_TYPE_BINARY_SENSOR:
        normalized_unit = None
    else:
        invert = False

    return ObjectModelEntityConfig(
        path=normalized_path,
        name=normalized_name,
        entity_type=entity_type,
        unit=normalized_unit,
        invert=invert,
    )


def object_model_configs_from_options(
    options: Mapping[str, Any],
) -> tuple[ObjectModelEntityConfig, ...]:
    """Return valid configured Object Model entities from config-entry options."""
    raw_entities = options.get(CONF_OBJECT_MODEL_ENTITIES, [])
    if not isinstance(raw_entities, list):
        return ()

    configs: list[ObjectModelEntityConfig] = []
    seen_paths: set[str] = set()
    for raw in raw_entities[:MAX_OBJECT_MODEL_ENTITIES]:
        if not isinstance(raw, dict):
            continue
        try:
            config = build_object_model_config(
                path=raw.get("path", ""),
                name=raw.get("name", ""),
                entity_type=raw.get("entity_type", ""),
                unit=raw.get("unit"),
                invert=raw.get("invert", False),
            )
        except AttributeError, TypeError, ValueError:
            continue
        if config.path in seen_paths:
            continue
        seen_paths.add(config.path)
        configs.append(config)

    return tuple(configs)


def options_with_object_model_configs(
    options: Mapping[str, Any],
    configs: tuple[ObjectModelEntityConfig, ...] | list[ObjectModelEntityConfig],
) -> dict[str, Any]:
    """Return a copy of options with the supplied Object Model configurations."""
    if len(configs) > MAX_OBJECT_MODEL_ENTITIES:
        raise ValueError("too many Object Model entities")
    updated = dict(options)
    updated[CONF_OBJECT_MODEL_ENTITIES] = [config.as_dict() for config in configs]
    return updated


def is_object_model_scalar(value: Any) -> bool:
    """Return whether a value can be represented as one HA scalar entity."""
    return value is None or isinstance(value, bool | int | float | str)


def object_model_sensor_value(value: Any) -> str | int | float | None:
    """Normalize a generic Object Model value for a Home Assistant sensor."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float | str):
        return value
    return None


def object_model_binary_value(value: Any, *, invert: bool = False) -> bool | None:
    """Normalize a generic Object Model value for a Home Assistant binary sensor."""
    parsed: bool | None = None
    if isinstance(value, bool):
        parsed = value
    elif isinstance(value, int | float) and not isinstance(value, bool):
        if value == 0:
            parsed = False
        elif value == 1:
            parsed = True
    elif isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in _TRUE_STRINGS:
            parsed = True
        elif normalized in _FALSE_STRINGS:
            parsed = False

    if parsed is None:
        return None
    return not parsed if invert else parsed
