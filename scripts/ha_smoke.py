#!/usr/bin/env python3
"""Network-free Home Assistant compatibility smoke test."""

from __future__ import annotations

import json
import pkgutil
import sys
from importlib import import_module, metadata
from pathlib import Path

from homeassistant.config_entries import ConfigFlow

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_PATH = ROOT / "custom_components" / "reprapfirmware"
PACKAGE = "custom_components.reprapfirmware"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    """Import the integration and every current Python module without network I/O."""
    manifest_path = INTEGRATION_PATH / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    import_module(PACKAGE)
    for module in pkgutil.iter_modules([str(INTEGRATION_PATH)]):
        import_module(f"{PACKAGE}.{module.name}")

    const = import_module(f"{PACKAGE}.const")
    config_flow = import_module(f"{PACKAGE}.config_flow")

    if manifest["domain"] != const.DOMAIN:
        raise AssertionError("Imported DOMAIN does not match manifest.json")

    if not issubclass(config_flow.RepRapFirmwareConfigFlow, ConfigFlow):
        raise AssertionError(
            "RepRapFirmwareConfigFlow is not a Home Assistant ConfigFlow"
        )

    print(f"Home Assistant: {metadata.version('homeassistant')}")
    print(f"RepRapFirmware integration: {manifest['version']}")
    print("Home Assistant import/API smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
