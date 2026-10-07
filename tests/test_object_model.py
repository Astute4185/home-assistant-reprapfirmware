"""Tests for configurable RepRapFirmware Object Model entities."""

from __future__ import annotations

import pytest

from custom_components.reprapfirmware.const import (
    CONF_OBJECT_MODEL_ENTITIES,
    ENTITY_TYPE_BINARY_SENSOR,
    ENTITY_TYPE_SENSOR,
    MAX_OBJECT_MODEL_ENTITIES,
)
from custom_components.reprapfirmware.object_model import (
    ObjectModelEntityConfig,
    build_object_model_config,
    is_object_model_scalar,
    normalize_object_model_path,
    object_model_binary_value,
    object_model_configs_from_options,
    object_model_sensor_value,
    options_with_object_model_configs,
)


def test_object_model_path_accepts_normal_rrf_keys() -> None:
    """Common dotted paths and numeric array indexes are accepted."""
    assert normalize_object_model_path(" global.fsRunoutSeq ") == "global.fsRunoutSeq"
    assert (
        normalize_object_model_path("sensors.gpIn[3].value") == "sensors.gpIn[3].value"
    )
    assert (
        normalize_object_model_path("boards[0].mcuTemp.current")
        == "boards[0].mcuTemp.current"
    )


@pytest.mark.parametrize(
    "path",
    ["", "global..value", "sensors.gpIn[x].value", "state status", ".state"],
)
def test_object_model_path_rejects_invalid_keys(path: str) -> None:
    """Malformed paths are rejected before they reach rr_model."""
    with pytest.raises(ValueError):
        normalize_object_model_path(path)


def test_build_sensor_config_normalizes_optional_values() -> None:
    """Sensor configuration trims names and units and ignores inversion."""
    config = build_object_model_config(
        path="global.filterHours",
        name=" Filter hours ",
        entity_type=ENTITY_TYPE_SENSOR,
        unit=" h ",
        invert=True,
    )

    assert config.name == "Filter hours"
    assert config.unit == "h"
    assert config.invert is False


def test_build_binary_config_drops_unit_and_preserves_inversion() -> None:
    """Binary configuration does not carry an invalid sensor unit."""
    config = build_object_model_config(
        path="global.doorOpen",
        name="Door",
        entity_type=ENTITY_TYPE_BINARY_SENSOR,
        unit="mm",
        invert=True,
    )

    assert config.unit is None
    assert config.invert is True


def test_entity_key_is_stable_for_path_and_independent_of_name() -> None:
    """Renaming a configured path does not replace the HA entity unique ID."""
    first = ObjectModelEntityConfig(
        path="global.fsRunoutSeq",
        name="Runout counter",
        entity_type=ENTITY_TYPE_SENSOR,
    )
    renamed = ObjectModelEntityConfig(
        path="global.fsRunoutSeq",
        name="Filament events",
        entity_type=ENTITY_TYPE_SENSOR,
    )

    assert first.entity_key == renamed.entity_key


def test_options_round_trip_preserves_other_options() -> None:
    """Object Model options are serialized without deleting unrelated settings."""
    configs = [
        build_object_model_config(
            path="global.fsRunoutSeq",
            name="Runout counter",
            entity_type=ENTITY_TYPE_SENSOR,
        ),
        build_object_model_config(
            path="global.fsBusy",
            name="Filament operation busy",
            entity_type=ENTITY_TYPE_BINARY_SENSOR,
            invert=True,
        ),
    ]
    options = options_with_object_model_configs({"other": "keep"}, configs)

    assert options["other"] == "keep"
    assert object_model_configs_from_options(options) == tuple(configs)


def test_options_parser_ignores_invalid_and_duplicate_entries() -> None:
    """Malformed persisted options cannot break integration setup."""
    options = {
        CONF_OBJECT_MODEL_ENTITIES: [
            {
                "path": "global.fsBusy",
                "name": "Busy",
                "entity_type": ENTITY_TYPE_BINARY_SENSOR,
            },
            {
                "path": "global.fsBusy",
                "name": "Duplicate",
                "entity_type": ENTITY_TYPE_SENSOR,
            },
            {"path": "bad path", "name": "Bad", "entity_type": ENTITY_TYPE_SENSOR},
            "not-a-dict",
        ]
    }

    configs = object_model_configs_from_options(options)

    assert len(configs) == 1
    assert configs[0].name == "Busy"


def test_options_enforce_entity_limit() -> None:
    """Configuration cannot create an unbounded number of rr_model reads."""
    configs = [
        ObjectModelEntityConfig(
            path=f"global.value{index}",
            name=f"Value {index}",
            entity_type=ENTITY_TYPE_SENSOR,
        )
        for index in range(MAX_OBJECT_MODEL_ENTITIES + 1)
    ]

    with pytest.raises(ValueError, match="too many"):
        options_with_object_model_configs({}, configs)


def test_scalar_detection_rejects_arrays_and_objects() -> None:
    """Only values representable by a single HA entity are accepted."""
    assert is_object_model_scalar(None)
    assert is_object_model_scalar(True)
    assert is_object_model_scalar(12)
    assert is_object_model_scalar(1.5)
    assert is_object_model_scalar("active")
    assert not is_object_model_scalar([])
    assert not is_object_model_scalar({"value": 1})


def test_sensor_value_rejects_boolean_and_complex_values() -> None:
    """Boolean values belong on binary sensors and complex values stay unsupported."""
    assert object_model_sensor_value(12) == 12
    assert object_model_sensor_value(1.5) == 1.5
    assert object_model_sensor_value("active") == "active"
    assert object_model_sensor_value(None) is None
    assert object_model_sensor_value(True) is None
    assert object_model_sensor_value([1]) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        (1, True),
        (0, False),
        (1.0, True),
        (0.0, False),
        ("true", True),
        ("ON", True),
        ("yes", True),
        ("false", False),
        ("OFF", False),
        ("no", False),
        (2, None),
        ("active", None),
        (None, None),
    ],
)
def test_binary_value_coercion(value: object, expected: bool | None) -> None:
    """Binary entities accept only explicit Boolean-like values."""
    assert object_model_binary_value(value) is expected


def test_binary_value_can_be_inverted() -> None:
    """Optional inversion is applied after binary coercion."""
    assert object_model_binary_value(1, invert=True) is False
    assert object_model_binary_value(0, invert=True) is True
    assert object_model_binary_value("unknown", invert=True) is None
