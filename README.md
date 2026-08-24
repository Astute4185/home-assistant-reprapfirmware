# RepRapFirmware Home Assistant Integration

<p align="center">
  <img src="custom_components/reprapfirmware/brand/icon@2x.png" width="128" alt="RepRapFirmware">
</p>

A Home Assistant custom integration for monitoring and controlling standalone **RepRapFirmware / Duet 3D printers** directly over the RepRapFirmware HTTP API.

Home Assistant communicates directly with the printer. No MQTT broker, intermediary service, Docker container or cloud component is required.

> **Status:** Active development. Core monitoring, machine control, macro discovery, printer events and fault detection are implemented.

## Features

### Printer monitoring

The integration exposes printer and job information including:

- online/offline state;
- RepRapFirmware machine status;
- current print job;
- print progress;
- print duration;
- estimated remaining time;
- current layer;
- file size;
- filament used;
- X, Y and Z position;
- current tool;
- fan speed and target;
- speed factor;
- extrusion factor.

### Temperature monitoring

Temperature entities include:

- nozzle temperature;
- nozzle target;
- bed temperature;
- bed target;
- MCU temperature.

Nozzle and bed temperature entities also expose the raw RepRapFirmware `heater_state` as an entity attribute.

This allows Home Assistant automations to detect RepRapFirmware heater faults directly.

### Diagnostics

Diagnostic data includes:

- MCU temperature;
- controller input voltage;
- printer uptime.

### Homing and filament monitoring

Binary sensors include:

- printer connectivity;
- X homed;
- Y homed;
- Z homed;
- filament monitor problem state, when a filament monitor is configured in RepRapFirmware.

The filament monitor entity exposes the raw RepRapFirmware monitor status as the `status` attribute.

Possible fault states include values such as:

- `noFilament`;
- `tooLittleMovement`;
- `tooMuchMovement`;
- `noDataReceived`;
- `sensorError`.

## Machine controls

The integration provides state-aware Home Assistant buttons for common printer operations.

| Control | RepRapFirmware command | Available when |
| --- | --- | --- |
| Home | `G28` | Idle |
| Pause | `M25` | Processing |
| Resume | `M24` | Paused |
| Cancel | `M0` | Processing or paused |

Buttons become unavailable when the current printer state does not permit the command.

This provides a basic safety layer against obviously inappropriate operations from a Home Assistant dashboard.

## RepRapFirmware macros

Top-level files in:

```text
/macros/
```

are automatically discovered and exposed as Home Assistant button entities.

For example:

```text
/macros/Delta Calibration.g
/macros/Load Filament.g
/macros/Unload Filament.g
```

become separate Home Assistant buttons.

Macros are refreshed:

- during integration setup;
- whenever the integration is reloaded;
- periodically while the integration is running.

Removed macros become unavailable rather than continuing to execute a stale path.

Nested macro directories are not currently supported.

## Printer events and notifications

The integration exposes a `Printer event` event entity intended for Home Assistant automations and notifications.

Supported event types are:

| Event | Description |
| --- | --- |
| `print_completed` | A print completed successfully |
| `printer_fault` | Heater, filament or generic machine fault |
| `print_paused` | An active print was paused |
| `printer_halted` | RepRapFirmware entered the halted state |
| `connection_lost_during_print` | Home Assistant lost contact with the printer during an active job |

### Fault events

`printer_fault` is the recommended event for fault notifications.

Fault events can include:

```text
fault_type
fault_source
fault_reason
```

For example:

```text
fault_type: heater
fault_source: nozzle
fault_reason: fault
```

or:

```text
fault_type: filament
fault_reason: noFilament
```

Fault events are edge-triggered so an unchanged fault does not generate a new notification on every polling cycle.

### Print completion

Completion events retain job information from the previous active print where available, including:

- job name;
- print duration;
- progress.

This allows notifications to retain useful job context even if RepRapFirmware clears the current job information when returning to idle.

Example automations are provided in:

```text
examples/notifications.yaml
```

## Home Assistant actions

Two advanced actions are provided.

### `reprapfirmware.run_macro`

Executes a currently discovered RepRapFirmware macro.

```yaml
action: reprapfirmware.run_macro
data:
  device_id: YOUR_HOME_ASSISTANT_DEVICE_ID
  macro: Delta Calibration.g
```

Macro matching is case-insensitive and the `.g` suffix may be omitted.

The requested macro must exist in the currently discovered RepRapFirmware macro list.

### `reprapfirmware.send_gcode`

Sends arbitrary G-code to the printer.

```yaml
action: reprapfirmware.send_gcode
data:
  device_id: YOUR_HOME_ASSISTANT_DEVICE_ID
  gcode: M122
```

This is an advanced action.

RepRapFirmware can execute arbitrary machine-control commands through this interface, so automations using `send_gcode` should be treated with the same care as commands entered directly into the Duet Web Control console.

## Requirements

Current target environment:

- RepRapFirmware **3.5+**;
- standalone RepRapFirmware / Duet HTTP API;
- current Home Assistant releases.

Development and testing are primarily performed against standalone Duet hardware.

## Installation

### HACS

Until the integration is available in the default HACS repository, add it as a custom repository.

1. Open **HACS** in Home Assistant.
2. Open **Custom repositories**.
3. Add this GitHub repository.
4. Select **Integration** as the repository type.
5. Install **RepRapFirmware**.
6. Restart Home Assistant when requested.

Then configure the integration through:

**Settings → Devices & services → Add integration → RepRapFirmware**

### Manual installation

Copy:

```text
custom_components/reprapfirmware
```

into your Home Assistant configuration:

```text
config/
└── custom_components/
    └── reprapfirmware/
```

Restart Home Assistant, then add the integration from **Settings → Devices & services**.

## Configuration

The integration is configured entirely through the Home Assistant UI.

Configuration fields include:

- Host/IP address;
- Port;
- HTTP or HTTPS;
- RepRapFirmware machine password;
- Optional display name.

The integration connects to RepRapFirmware using its HTTP session API and retains the session key only in memory.

## Polling

The integration uses Home Assistant's coordinated polling model rather than allowing individual entities to independently query the printer.

Typical polling behaviour is:

- active, printing or transitional states: approximately every 5 seconds;
- idle state: approximately every 20 seconds;
- offline state: progressively backed-off retries up to approximately 60 seconds.

When communication is lost, normal printer entities become unavailable while the connectivity binary sensor remains available and reports the printer as offline.

## Dashboard example

A mobile-friendly dashboard example using built-in Home Assistant cards is available at:

```text
examples/dashboard.yaml
```

It demonstrates:

- printer status;
- current job information;
- temperatures;
- Pause / Resume / Cancel controls;
- Home;
- discovered macro buttons;
- an Open DWC link;
- offline handling.

Entity IDs and the Duet Web Control address must be adjusted for your printer.

## Duet Web Control

This integration is intended to complement **Duet Web Control**, not replace it.

DWC remains the appropriate interface for:

- configuration;
- console access;
- file management;
- firmware management;
- diagnostics;
- height maps;
- advanced machine control.

Home Assistant provides monitoring, automation, notifications and convenient commonly used controls around that existing interface.

## Development

Bootstrap the local development environment:

```bash
scripts/bootstrap
source .venv/bin/activate
```

Run the normal repository validation:

```bash
scripts/check
```

Run the extended validation suite:

```bash
scripts/check-all
```

The validation stack includes:

- repository structure checks;
- Ruff;
- pytest;
- Home Assistant import/API smoke testing;
- dependency validation;
- Home Assistant Hassfest;
- HACS validation in CI.

Pull requests targeting `main` must pass the configured repository, Hassfest and HACS validation gates before merge.

## Contributing

Bug reports and pull requests are welcome.

Changes should preserve the integration's core design:

- direct local communication with RepRapFirmware;
- Home Assistant-native entities and configuration;
- no mandatory intermediary service;
- state-aware machine controls;
- safe handling of arbitrary commands and macro paths.

Contributions should not copy third-party source code unless licence compatibility and attribution requirements have been reviewed.

## Disclaimer

This is an independent, community-developed project.

It is not affiliated with, endorsed by, sponsored by or maintained by Home Assistant, Nabu Casa, Duet3D or the RepRapFirmware project.

Home Assistant, RepRapFirmware, Duet, Duet3D and other third-party project names are used only to identify compatibility and interoperability with the systems this integration supports.

See `THIRD_PARTY_NOTICES.md` for third-party licence and attribution information.

## Licence

Original source code in this repository is licensed under the **Apache License 2.0** unless otherwise noted.

See `LICENSE` for details.