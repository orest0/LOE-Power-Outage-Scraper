"""Coordinator for LOE Power Outage."""

from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_INTERVAL, CONF_URL, DOMAIN
from .sensor import parse_outage_page, PowerOutageGroup

_LOGGER = logging.getLogger(__name__)

DEFAULT_JSON_PATH = "/home/pi/power_outages/data/outages.json"


class PowerOutageCoordinator(DataUpdateCoordinator):
    """Class to manage fetching power outage data."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize."""
        self.hass = hass
        self.config = config
        self.json_path = config.get("json_file", DEFAULT_JSON_PATH)
        self.interval = config.get(CONF_INTERVAL, 10)

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=self.interval),
        )

        self.groups: list[PowerOutageGroup] = []
        self._last_updated = None

    async def _async_update_data(self) -> dict:
        """Update data from JSON file."""
        try:
            json_file = Path(self.json_path)

            if not json_file.exists():
                _LOGGER.warning(f"JSON file not found: {self.json_path}")
                return {"groups": [], "last_updated": None}

            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            last_updated = data.get("last_updated", datetime.now().isoformat())

            groups = []
            for group_data in data.get("outage_groups", []):
                group = PowerOutageGroup(group_data.get("group", ""))
                group.outages_today = group_data.get("outages_today", [])
                group.outages_tomorrow = group_data.get("outages_tomorrow", [])
                groups.append(group)

            self.groups = groups

            _LOGGER.info(
                f"Loaded {len(self.groups)} outage groups from {self.json_path}"
            )

            return {
                "groups": self.groups,
                "last_updated": last_updated,
            }

        except Exception as e:
            _LOGGER.error(f"Error loading data: {e}")
            return {"groups": [], "last_updated": None}
