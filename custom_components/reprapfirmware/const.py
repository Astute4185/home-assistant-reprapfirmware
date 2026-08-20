"""Constants for the RepRapFirmware integration."""

from datetime import timedelta

DOMAIN = "reprapfirmware"

CONF_USE_SSL = "use_ssl"

ATTR_GCODE = "gcode"
ATTR_MACRO = "macro"
SERVICE_RUN_MACRO = "run_macro"
SERVICE_SEND_GCODE = "send_gcode"

EVENT_PRINT_COMPLETED = "print_completed"
EVENT_PRINT_PAUSED = "print_paused"
EVENT_PRINTER_HALTED = "printer_halted"
EVENT_CONNECTION_LOST_DURING_PRINT = "connection_lost_during_print"
PRINTER_EVENT_TYPES = (
    EVENT_PRINT_COMPLETED,
    EVENT_PRINT_PAUSED,
    EVENT_PRINTER_HALTED,
    EVENT_CONNECTION_LOST_DURING_PRINT,
)

DEFAULT_NAME = "RepRapFirmware"
DEFAULT_PORT_HTTP = 80
DEFAULT_PORT_HTTPS = 443
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_REPLY_TIMEOUT = 2.0
DEFAULT_REPLY_POLL_INTERVAL = 0.05

MACRO_DIRECTORY = "/macros/"
MACRO_REFRESH_INTERVAL = timedelta(minutes=5)

ACTIVE_POLL_INTERVAL = timedelta(seconds=5)
IDLE_POLL_INTERVAL = timedelta(seconds=20)
MIN_OFFLINE_RETRY_INTERVAL = timedelta(seconds=10)
MAX_OFFLINE_RETRY_INTERVAL = timedelta(seconds=60)

ACTIVE_PRINTER_STATES = frozenset(
    {
        "busy",
        "cancelling",
        "changingTool",
        "pausing",
        "paused",
        "processing",
        "resuming",
        "simulating",
        "starting",
    }
)
