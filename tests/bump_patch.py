#!/usr/bin/env python3
"""Increment the custom integration patch version in manifest.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "custom_components" / "reprapfirmware" / "manifest.json"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def main() -> None:
    """Increment the manifest patch version and print the new version."""
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    current = manifest["version"]

    match = SEMVER.fullmatch(current)
    if match is None:
        raise SystemExit(f"manifest version is not valid SemVer: {current!r}")

    major, minor, patch = (int(part) for part in match.groups())
    new_version = f"{major}.{minor}.{patch + 1}"

    manifest["version"] = new_version
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(new_version)


if __name__ == "__main__":
    main()
