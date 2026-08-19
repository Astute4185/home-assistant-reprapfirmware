"""Constants for the RepRapFirmware integration."""

from datetime import timedelta

DOMAIN = "reprapfirmware"

CONF_USE_SSL = "use_ssl"

DEFAULT_NAME = "RepRapFirmware"
DEFAULT_PORT_HTTP = 80
DEFAULT_PORT_HTTPS = 443
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_REPLY_TIMEOUT = 2.0
DEFAULT_REPLY_POLL_INTERVAL = 0.05

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
