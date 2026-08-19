#!/usr/bin/env python3
"""Validate repository invariants without starting Home Assistant."""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "reprapfirmware"
INTEGRATION = ROOT / "custom_components" / DOMAIN
MANIFEST = INTEGRATION / "manifest.json"
RUNTIME_REQUIREMENTS = ROOT / "requirements-runtime.txt"

REQUIRED_ROOT_FILES = (
    "LICENSE",
    "NOTICE",
    "README.md",
    "THIRD_PARTY_NOTICES.md",
    "requirements-runtime.txt",
    "requirements-test.txt",
)
REQUIRED_INTEGRATION_FILES = (
    "__init__.py",
    "api.py",
    "config_flow.py",
    "const.py",
    "manifest.json",
    "strings.json",
    "translations/en.json",
)
REQUIRED_MANIFEST_KEYS = {
    "config_flow",
    "domain",
    "integration_type",
    "iot_class",
    "name",
    "requirements",
    "version",
}
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def _load_json(path: Path) -> Any:
    """Load JSON and report a useful path if it is malformed."""
    try:
        with path.open(encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except (OSError, json.JSONDecodeError) as err:
        relative_path = path.relative_to(ROOT)
        raise ValueError(f"Cannot load valid JSON from {relative_path}: {err}") from err


def _runtime_requirements() -> list[str]:
    """Return non-comment runtime requirements."""
    return [
        line.strip()
        for line in RUNTIME_REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _domain_from_const() -> str | None:
    """Read DOMAIN from const.py without importing Home Assistant."""
    tree = ast.parse((INTEGRATION / "const.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        is_domain = any(
            isinstance(target, ast.Name) and target.id == "DOMAIN"
            for target in node.targets
        )
        if not is_domain:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node.value.value
    return None


def main() -> int:
    """Run repository-level checks."""
    errors: list[str] = []

    for relative_path in REQUIRED_ROOT_FILES:
        if not (ROOT / relative_path).is_file():
            errors.append(f"missing required repository file: {relative_path}")

    for relative_path in REQUIRED_INTEGRATION_FILES:
        if not (INTEGRATION / relative_path).is_file():
            errors.append(
                "missing required integration file: "
                f"custom_components/{DOMAIN}/{relative_path}"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        manifest = _load_json(MANIFEST)
        strings = _load_json(INTEGRATION / "strings.json")
        english = _load_json(INTEGRATION / "translations" / "en.json")
    except ValueError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    if not isinstance(manifest, dict):
        errors.append("manifest.json must contain a JSON object")
    else:
        missing = sorted(REQUIRED_MANIFEST_KEYS - manifest.keys())
        if missing:
            errors.append(f"manifest.json missing keys: {', '.join(missing)}")

        if manifest.get("domain") != DOMAIN:
            errors.append("manifest domain does not match integration directory")
        if manifest.get("name") != "RepRapFirmware":
            errors.append("manifest name must be RepRapFirmware")
        if manifest.get("config_flow") is not True:
            errors.append("manifest config_flow must be true")
        if manifest.get("integration_type") != "device":
            errors.append("manifest integration_type must be device")
        if manifest.get("iot_class") != "local_polling":
            errors.append("manifest iot_class must be local_polling")

        version = manifest.get("version")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            errors.append(
                "manifest version must be a SemVer-style string such as 0.0.1"
            )

        requirements = manifest.get("requirements")
        if not isinstance(requirements, list) or not all(
            isinstance(item, str) for item in requirements
        ):
            errors.append("manifest requirements must be a list of strings")
        elif requirements != _runtime_requirements():
            errors.append(
                "requirements-runtime.txt must exactly match manifest.json requirements"
            )

    const_domain = _domain_from_const()
    if const_domain != DOMAIN:
        errors.append(f"const.py DOMAIN must be {DOMAIN!r}; found {const_domain!r}")

    if strings != english:
        errors.append(
            "translations/en.json must match strings.json until translations are "
            "generated separately"
        )

    runtime_text = "\n".join(_runtime_requirements()).lower()
    for supplied_by_ha in ("aiohttp", "homeassistant"):
        if supplied_by_ha in runtime_text:
            errors.append(
                f"{supplied_by_ha} is supplied by the Home Assistant runtime and "
                "must not be a runtime requirement"
            )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print("Repository metadata validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
