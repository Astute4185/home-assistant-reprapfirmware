# Third-Party Notices

This document records third-party projects, interfaces, definitions, libraries, and source material relevant to **home-assistant-reprapfirmware**.

The presence of a project in this document does **not** mean that its source code is bundled, copied, or redistributed by this repository.

## Home Assistant

This project is designed as a custom integration for Home Assistant.

Home Assistant Core is distributed under the Apache License 2.0.

- Project: Home Assistant Core
- License: Apache-2.0
- Source: https://github.com/home-assistant/core
- Developer documentation: https://developers.home-assistant.io/

This project may use Home Assistant's documented integration APIs, entity definitions, configuration patterns, and other public interfaces required to implement a Home Assistant custom integration.

This project is independent and is not affiliated with, endorsed by, sponsored by, or maintained by Home Assistant or Nabu Casa.

## RepRapFirmware

This project interoperates with RepRapFirmware through its HTTP API, Object Model, G-code interfaces, and related documented behaviour.

RepRapFirmware source files are distributed under the GNU General Public License version 3.

- Project: RepRapFirmware
- License: GPL-3.0
- Source: https://github.com/Duet3D/RepRapFirmware
- Documentation: https://docs.duet3d.com/

RepRapFirmware is **not** included or redistributed as part of this repository.

This project's own implementation should be written independently against documented interfaces. Any future copying or adaptation of RepRapFirmware source code must be reviewed separately for licence compatibility and attribution requirements before inclusion.

## Duet3D and Duet Web Control

This project is intended to operate with compatible standalone Duet controllers running RepRapFirmware and to complement, rather than replace, Duet Web Control.

Duet3D software and related projects are separate works maintained under their respective licences.

- Organisation: https://github.com/Duet3D
- Documentation: https://docs.duet3d.com/

No Duet3D or Duet Web Control source code is included in this repository unless explicitly identified in a future notice.

This project is independent and is not affiliated with, endorsed by, sponsored by, or maintained by Duet3D.

## Third-party Python libraries

At repository creation, no additional third-party Python client library is bundled by this project.

When dependencies are introduced, their package name, source project, licence, and any attribution or redistribution obligations should be reviewed and recorded here when required.

## Definitions, schemas, constants, and interoperability

Names of API endpoints, Object Model fields, G-code commands, entity concepts, protocol fields, and other compatibility identifiers may appear in this project where required to communicate with or represent supported systems.

Such compatibility references do not imply ownership of, affiliation with, or endorsement by the respective projects.

## Maintainer note

Before incorporating code from another repository:

1. Identify the exact source and licence.
2. Confirm that the licence is compatible with this repository's Apache-2.0 licensing model.
3. Preserve required copyright, licence, and attribution notices.
4. Record material reused or redistributed components in this file where appropriate.
5. Do not assume that publicly visible source code can be copied into this project without licence review.
