"""Tests for RepRapFirmware macro discovery helpers."""

from custom_components.reprapfirmware.api import RepRapFirmwareFileItem
from custom_components.reprapfirmware.macro import discover_macros


def _item(name: str, *, item_type: str = "f") -> RepRapFirmwareFileItem:
    return RepRapFirmwareFileItem(name=name, item_type=item_type, size=1)


def test_discovery_supports_extensionless_macro_files() -> None:
    """RRF user macros do not require a .g extension."""
    macros = discover_macros(
        (
            _item("Calibrate Printer"),
            _item("PID Tune.G"),
            _item("Wifi Reset"),
            _item("Subfolder", item_type="d"),
            _item("nested/test.g"),
            _item('bad"name.g'),
        )
    )

    assert [macro.name for macro in macros] == [
        "Calibrate Printer",
        "PID Tune.G",
        "Wifi Reset",
    ]


def test_macro_builds_standard_m98_command_for_extensionless_file() -> None:
    """Extensionless discovered macros execute their real RRF path."""
    (macro,) = discover_macros((_item("Calibrate Printer"),))

    assert macro.path == "/macros/Calibrate Printer"
    assert macro.display_name == "Calibrate Printer"
    assert macro.gcode == 'M98 P"/macros/Calibrate Printer"'


def test_macro_display_name_strips_g_extension_only_when_present() -> None:
    """Existing .g macro filenames keep the prior friendly display behaviour."""
    (macro,) = discover_macros((_item("Delta Calibration.g"),))

    assert macro.display_name == "Delta Calibration"


def test_macro_resolution_accepts_path_case_and_g_aliases() -> None:
    """Actions may identify extensionless macros with or without .g."""
    (macro,) = discover_macros((_item("Calibrate Printer"),))

    assert macro.matches("Calibrate Printer")
    assert macro.matches("Calibrate Printer.g")
    assert macro.matches("calibrate printer")
    assert macro.matches("/macros/Calibrate Printer")
    assert macro.matches("/macros/Calibrate Printer.g")
    assert not macro.matches("Wifi Reset")
    assert not macro.matches("../Calibrate Printer")


def test_g_extension_macro_resolution_accepts_extensionless_alias() -> None:
    """Legacy .g macros can also be addressed without typing the extension."""
    (macro,) = discover_macros((_item("Delta Calibration.g"),))

    assert macro.matches("Delta Calibration.g")
    assert macro.matches("Delta Calibration")


def test_macro_entity_key_is_stable_and_path_specific() -> None:
    """Macro entity unique-id suffixes are deterministic but filename-safe."""
    (first,) = discover_macros((_item("Delta Calibration.g"),))
    (same,) = discover_macros((_item("Delta Calibration.g"),))
    (other,) = discover_macros((_item("PID Tune.g"),))

    assert first.entity_key == same.entity_key
    assert first.entity_key != other.entity_key
    assert first.entity_key.startswith("macro_")


def test_exact_macro_names_remain_distinguishable_when_both_alias_forms_exist() -> None:
    """A printer may contain both Foo and Foo.g; exact names must stay distinct."""
    extensionless, with_extension = discover_macros(
        (_item("Calibrate Printer"), _item("Calibrate Printer.g"))
    )

    assert extensionless.exact_matches("Calibrate Printer")
    assert not extensionless.exact_matches("Calibrate Printer.g")
    assert with_extension.exact_matches("Calibrate Printer.g")
    assert not with_extension.exact_matches("Calibrate Printer")
