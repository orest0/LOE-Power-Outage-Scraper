"""Coordinator for LOE Power Outage."""

from datetime import datetime, timedelta
import logging
import json
from pathlib import Path
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_INTERVAL, CONF_URL, DOMAIN
from .sensor import parse_outage_page, PowerOutageGroup

_LOGGER = logging.getLogger(__name__)

DEFAULT_JSON_PATH = "/config/data/outages.json"
CONF_JSON_URL = "json_url"


class PowerOutageCoordinator(DataUpdateCoordinator):
    """Class to manage fetching power outage data."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize."""
        self.hass = hass
        self.config = config
        self.json_url = config.get(CONF_JSON_URL, "")
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
        """Update data from JSON file or URL."""
        try:
            if self.json_url:
                return await self._load_from_url(self.json_url)
            else:
                return await self._load_from_file()

        except Exception as e:
            _LOGGER.error(f"Error loading data: {e}")
            return {"groups": [], "last_updated": None}

    async def _load_from_url(self, url: str) -> dict:
        """Load data from HTTP URL."""
        _LOGGER.info(f"Loading data from URL: {url}")

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    _LOGGER.error(f"HTTP error: {response.status}")
                    return {"groups": [], "last_updated": None}

                data = await response.json()

        return self._parse_data(data)

    async def _load_from_file(self) -> dict:
        """Load data from local JSON file."""
        json_file = Path(self.json_path)

        if not json_file.exists():
            _LOGGER.warning(f"JSON file not found: {self.json_path}")
            return {"groups": [], "last_updated": None}

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self._parse_data(data)

    def _parse_data(self, data: dict) -> dict:
        """Parse JSON data into groups."""
        last_updated = data.get("last_updated", datetime.now().isoformat())

        groups = []
        for group_data in data.get("outage_groups", []):
            group = PowerOutageGroup(group_data.get("group", ""))
            group.outages_today = group_data.get("outages_today", [])
            group.outages_tomorrow = group_data.get("outages_tomorrow", [])
            groups.append(group)

        self.groups = groups

        _LOGGER.info(f"Loaded {len(self.groups)} outage groups")

        return {
            "groups": self.groups,
            "last_updated": last_updated,
        }
