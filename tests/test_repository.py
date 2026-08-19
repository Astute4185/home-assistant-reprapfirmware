"""Baseline repository tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "reprapfirmware"


def test_manifest_identity() -> None:
    """The package path and manifest must keep the permanent HA domain."""
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    assert INTEGRATION.name == "reprapfirmware"
    assert manifest["domain"] == "reprapfirmware"
    assert manifest["name"] == "RepRapFirmware"


def test_english_translation_tracks_source_strings() -> None:
    """English translation must not drift from source strings during bootstrap."""
    strings = json.loads((INTEGRATION / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (INTEGRATION / "translations" / "en.json").read_text(encoding="utf-8")
    )

    assert english == strings
