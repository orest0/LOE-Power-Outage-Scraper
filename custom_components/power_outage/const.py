"""Constants for LOE Power Outage."""

DOMAIN = "power_outage"

DEFAULT_URL = "https://poweron.loe.lviv.ua"
DEFAULT_INTERVAL = 10
DEFAULT_JSON_PATH = "/home/pi/loe_telegram_bot/data/outages.json"

CONF_URL = "url"
CONF_INTERVAL = "interval"
CONF_GROUPS = "groups"
CONF_JSON_FILE = "json_file"

ALL_GROUPS = [
    "1.1",
    "1.2",
    "2.1",
    "2.2",
    "3.1",
    "3.2",
    "4.1",
    "4.2",
    "5.1",
    "5.2",
    "6.1",
    "6.2",
]
