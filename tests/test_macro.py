"""Tests for RepRapFirmware macro discovery helpers."""

from custom_components.reprapfirmware.api import RepRapFirmwareFileItem
from custom_components.reprapfirmware.macro import discover_macros


def _item(name: str, *, item_type: str = "f") -> RepRapFirmwareFileItem:
    return RepRapFirmwareFileItem(name=name, item_type=item_type, size=1)


def test_discovery_exposes_only_top_level_g_files() -> None:
    """P3 ignores directories, non-G-code files, and unsafe/nested names."""
    macros = discover_macros(
        (
            _item("Delta Calibration.g"),
            _item("PID Tune.G"),
            _item("notes.txt"),
            _item("Subfolder", item_type="d"),
            _item("nested/test.g"),
            _item('bad"name.g'),
        )
    )

    assert [macro.name for macro in macros] == [
        "Delta Calibration.g",
        "PID Tune.G",
    ]


def test_macro_builds_standard_m98_command() -> None:
    """Discovered macro execution uses the project-defined M98 path form."""
    (macro,) = discover_macros((_item("Delta Calibration.g"),))

    assert macro.path == "/macros/Delta Calibration.g"
    assert macro.display_name == "Delta Calibration"
    assert macro.gcode == 'M98 P"/macros/Delta Calibration.g"'


def test_macro_entity_key_is_stable_and_path_specific() -> None:
    """Macro entity unique-id suffixes are deterministic but filename-safe."""
    (first,) = discover_macros((_item("Delta Calibration.g"),))
    (same,) = discover_macros((_item("Delta Calibration.g"),))
    (other,) = discover_macros((_item("PID Tune.g"),))

    assert first.entity_key == same.entity_key
    assert first.entity_key != other.entity_key
    assert first.entity_key.startswith("macro_")
