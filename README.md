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

## Current repository baseline

The repository currently contains the legal/project baseline and a minimal Home Assistant custom-integration scaffold. The configuration flow stores endpoint details but **does not yet validate or connect to the printer**. Network authentication and validation belong to the P0 API-client milestone.

## Disclaimer

This is an independent, community-developed project. It is **not affiliated with, endorsed by, sponsored by, or maintained by Home Assistant, Nabu Casa, Duet3D, or the RepRapFirmware project**.

Home Assistant, RepRapFirmware, Duet, Duet3D, and other third-party project names are used only to identify compatibility and interoperability with the systems this integration is designed to support.

This project interacts with third-party systems through their documented interfaces and may use third-party open-source libraries. Those projects and libraries remain subject to their own copyright and licence terms. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Licence

Unless otherwise noted, original source code in this repository is licensed under the **Apache License 2.0**. See [LICENSE](LICENSE).

Third-party software is not relicensed by this repository. Any incorporated or redistributed third-party material remains subject to its applicable licence and attribution requirements.

## Contributions

Contributions should avoid copying code from third-party repositories unless the source, licence compatibility, and required attribution have been reviewed first.
