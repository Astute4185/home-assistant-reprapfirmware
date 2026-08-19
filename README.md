# RepRapFirmware Home Assistant Integration

A Home Assistant custom integration for monitoring and controlling standalone RepRapFirmware/Duet 3D printers directly over the RepRapFirmware HTTP API.

> **Project status:** Early development / proof of concept.

## Objective

The project is intended to provide a native-style Home Assistant integration for RepRapFirmware printers while keeping Duet Web Control available for configuration, console access, file management, diagnostics, height maps, and other advanced machine operations.

Planned capabilities include:

- printer online/offline and machine-state monitoring;
- print job name, progress, duration, remaining time, layer, and file metadata;
- nozzle, bed, and additional heater temperatures;
- machine position and selected operating state;
- Home, Pause, Resume, and Cancel controls;
- automatic discovery of RepRapFirmware macros as Home Assistant buttons;
- advanced Home Assistant actions for running macros and sending G-code;
- state suitable for completion, pause, fault, and connection-loss automations;
- a mobile-friendly example Home Assistant dashboard.

## Home Assistant domain

```text
reprapfirmware
```

The domain intentionally refers to RepRapFirmware rather than a specific Duet controller model.

## Initial target

- RepRapFirmware 3.5+
- standalone Duet HTTP API
- Duet 3 Mini 5+ WiFi as the primary development platform
- current Home Assistant releases

## Architecture

Home Assistant will communicate directly with RepRapFirmware. The project does not require an MQTT broker, intermediary Docker service, or cloud component.

The planned integration package is:

```text
custom_components/
└── reprapfirmware/
    ├── __init__.py
    ├── manifest.json
    ├── const.py
    ├── config_flow.py
    ├── api.py
    ├── coordinator.py
    ├── entity.py
    ├── sensor.py
    ├── binary_sensor.py
    ├── button.py
    ├── diagnostics.py
    ├── services.yaml
    ├── strings.json
    └── translations/
        └── en.json
```

## POC milestones

1. **API client** — authentication, session handling, Object Model reads, G-code submission, command replies, reconnect handling.
2. **Home Assistant device** — UI config flow and core status/job/temperature entities.
3. **Machine control** — Home, Pause, Resume, Cancel, and advanced G-code action.
4. **Macro support** — enumerate `/macros/`, create macro buttons, run macros, refresh discovery.
5. **Notifications and dashboard** — expose reliable state transitions and example automations/dashboard configuration.
6. **Hardening** — timeouts, unavailable state, malformed responses, diagnostics, tests, and distribution readiness.

## Current implementation status

**P0 — API client implementation is present.** The integration now has an asynchronous RepRapFirmware HTTP client with session-key authentication, Object Model reads, G-code submission, command-reply retrieval, disconnect/reconnect handling, and config-flow connection validation. Unit and repository validation can be completed locally; live printer acceptance is required before P0 is considered complete.

The Home Assistant device, coordinator, entities, machine-control buttons, macro entities, and notification/dashboard work remain later milestones.

## Disclaimer

This is an independent, community-developed project. It is **not affiliated with, endorsed by, sponsored by, or maintained by Home Assistant, Nabu Casa, Duet3D, or the RepRapFirmware project**.

Home Assistant, RepRapFirmware, Duet, Duet3D, and other third-party project names are used only to identify compatibility and interoperability with the systems this integration is designed to support.

This project interacts with third-party systems through their documented interfaces and may use third-party open-source libraries. Those projects and libraries remain subject to their own copyright and licence terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licence

Unless otherwise noted, original source code in this repository is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

Third-party software is not relicensed by this repository. Any incorporated or redistributed third-party material remains subject to its applicable licence and attribution requirements.

## Contributions

Contributions should avoid copying code from third-party repositories unless the source, licence compatibility, and required attribution have been reviewed first.

## Development validation

The repository includes a small validation harness so structural and compatibility issues can be caught before printer-facing development starts.

Requirements:

- Python 3.14.2 or newer;
- Docker only for local `hassfest` and fallback GitHub Actions linting.

Bootstrap the local environment:

```bash
scripts/bootstrap
source .venv/bin/activate
```

Run the normal local gate:

```bash
scripts/check
```

This runs repository validation, Ruff, pytest, the network-free Home Assistant import smoke test, and dependency checks.

Run the extended gate:

```bash
scripts/check-all
```

The extended gate also runs the official Home Assistant `hassfest` container and validates GitHub Actions workflows. CI runs the repository checks and official `hassfest` validation automatically on pushes and pull requests.

Useful individual commands:

```text
scripts/lint          Static repository checks, Ruff, and Python compilation
scripts/test          Pytest suite
scripts/smoke         Network-free Home Assistant import/API smoke test
scripts/dependencies  pip dependency integrity and runtime dependency audit
scripts/hassfest      Official Home Assistant hassfest validation via Docker
scripts/workflow-lint GitHub Actions workflow validation
scripts/p0-probe      Live P0 acceptance probe against a RepRapFirmware controller
```

### P0 live acceptance probe

After the normal validation gate passes, validate the API client against a real printer:

```bash
export RRF_PASSWORD='your-machine-password'
scripts/p0-probe 192.168.1.50
```

For HTTPS or a non-default port:

```bash
scripts/p0-probe printer.local --https --port 443
```

If `RRF_PASSWORD` is not set, the probe prompts for the machine password without placing it in the command line. A successful P0 probe connects with a session key, reads `state.status`, sends `M115`, receives its firmware reply, and disconnects.
