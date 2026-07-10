"""Constants for the Intel AMT integration."""

DOMAIN = "intel_amt"

CONF_PROTOCOL = "protocol"
CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_NAME = "name"

DEFAULT_USERNAME = "admin"
DEFAULT_PROTOCOL = "http"
DEFAULT_SCAN_INTERVAL = 120

PROTOCOL_HTTP = "http"
PROTOCOL_HTTPS = "https"

PORT_HTTP = 16992
PORT_HTTPS = 16993

POWER_STATES = {
    "on": 2,
    "standby": 3,
    "sleep": 4,
    "reboot": 5,
    "hibernate": 7,
    "off": 8,
    "hard-reboot": 9,
    "reset": 10,
    "nmi": 11,
    "soft-off": 12,
    "soft-reset": 14,
}

RETURN_VALUES = {
    0: "success",
    1: "not supported",
    2: "not ready",
    3: "timeout",
    4: "failed",
    5: "invalid parameter",
    6: "in use",
}
