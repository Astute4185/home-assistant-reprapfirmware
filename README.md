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
    ├── event.py
    ├── events.py
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

**P4 — notifications and dashboard implementation is present.** The integration includes the P0 API/session layer, P1 Home Assistant device entities, P2 machine controls, P3 top-level RepRapFirmware macro discovery, and P4 printer transition events plus example notification/dashboard configuration.

Distribution hardening remains the final POC milestone.

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

### P1 Home Assistant acceptance

After `scripts/check-all` passes, copy or mount `custom_components/reprapfirmware` into a test Home Assistant configuration and restart Home Assistant. Add **RepRapFirmware** from **Settings → Devices & services** using the real printer connection details.

P1 is accepted when one printer device is created and the online/status/job/temperature entities show live values without YAML configuration. When RepRapFirmware exposes `boards[0].uniqueId`, that hardware ID is used as the stable Home Assistant config-entry/device identity. While the printer is in an active or transitional state (`processing`, `paused`, `busy`, `pausing`, `resuming`, `cancelling`, `changingTool`, `simulating`, or `starting`), the coordinator polls every 5 seconds; otherwise it polls every 20 seconds. If communication is lost after setup, normal entities become unavailable and the Online binary sensor reports off while retry intervals back off up to 60 seconds.

## P2 machine control

P2 adds state-aware Home Assistant button entities for the standard printer controls:

| Control | RepRapFirmware command | Available state |
|---|---|---|
| Home | `G28` | `idle` |
| Pause | `M25` | `processing` |
| Resume | `M24` | `paused` |
| Cancel | `M0` | `processing`, `paused` |

The integration also registers the advanced `reprapfirmware.send_gcode` action. It targets a RepRapFirmware device by Home Assistant `device_id` and can optionally return the RepRapFirmware command reply when the caller requests response data.

```yaml
action: reprapfirmware.send_gcode
data:
  device_id: YOUR_HOME_ASSISTANT_DEVICE_ID
  gcode: M122
response_variable: rrf_response
```

After each control or arbitrary G-code submission, the coordinator requests an immediate refresh so Home Assistant can reflect the resulting machine state without waiting for the normal polling interval.


## P3 macro support

P3 discovers top-level macro files from `/macros/` using RepRapFirmware's `/rr_filelist` endpoint. File-list pagination is followed until `next` is zero. RepRapFirmware user macros may be named with or without a `.g` extension, so every safe top-level regular file is eligible; directories and nested paths are ignored. Nested macro directories remain out of scope for the POC.

Each discovered macro is exposed as a Home Assistant button. For example, `/macros/Delta Calibration.g` is executed with:

```gcode
M98 P"/macros/Delta Calibration.g"
```

Macro discovery runs during integration setup, again whenever the config entry is reloaded, and every five minutes while the integration is loaded. Newly discovered macros are added as button entities. If a macro is removed from the printer, its existing Home Assistant button becomes unavailable instead of executing a stale path.

The integration also registers `reprapfirmware.run_macro`:

```yaml
action: reprapfirmware.run_macro
data:
  device_id: YOUR_HOME_ASSISTANT_DEVICE_ID
  macro: Calibrate Printer
```

The action resolves the requested value against the currently discovered macro list. Macro names are matched case-insensitively and `.g` is treated as an optional alias, so an extensionless `Calibrate Printer` macro may be called using either `Calibrate Printer` or `Calibrate Printer.g`. If no discovered macro matches, the integration performs one immediate macro refresh before returning a validation error. This prevents the action from being used as an unrestricted path/G-code injection mechanism.

## P4 notifications and dashboard

P4 adds a `Printer event` event entity for one-shot printer lifecycle signals. The event entity exposes these event types:

- `print_completed` for a direct `processing` → `idle` transition;
- `print_paused` for a direct `processing` → `paused` transition;
- `printer_halted` whenever the printer enters `halted`;
- `connection_lost_during_print` when coordinator communication changes from online to unavailable while the last known printer state was `processing`.

Completion events retain the previous active job name, duration, and progress because RepRapFirmware may clear job data when it returns to idle. If connectivity is lost during a print, P4 deliberately suppresses completion/pause inference on the first recovered sample because the missing interval makes that transition ambiguous. A later successful sample re-establishes the normal transition baseline.

Example Home Assistant configuration is provided in:

```text
examples/notifications.yaml
examples/dashboard.yaml
```

The notification examples target a placeholder Companion App notify action and must be edited to use the actual printer event entity and phone notify action. The dashboard example uses only built-in Home Assistant cards, includes state-aware printer controls, macro buttons, and an Open DWC link, and should likewise be updated with the actual entity IDs and DWC URL.
