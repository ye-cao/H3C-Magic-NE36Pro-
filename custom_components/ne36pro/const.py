"""Constants for the H3C Magic NE36Pro integration."""
from __future__ import annotations

DOMAIN = "ne36pro"
DEFAULT_NAME = "H3C Magic NE36Pro"
DEFAULT_USERNAME = "user"

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

PLATFORMS = ["sensor", "binary_sensor", "switch", "button", "device_tracker"]

UPDATE_INTERVAL = 30  # seconds
