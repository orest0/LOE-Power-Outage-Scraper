"""Coordinator for LOE Power Outage."""

from datetime import datetime, timedelta
import logging
import asyncio
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_INTERVAL, CONF_URL, DOMAIN
from .sensor import parse_outage_page, PowerOutageGroup

_LOGGER = logging.getLogger(__name__)


class PowerOutageCoordinator(DataUpdateCoordinator):
    """Class to manage fetching power outage data."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize."""
        self.hass = hass
        self.config = config
        self.url = config.get(CONF_URL, "https://poweron.loe.lviv.ua")
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
        """Update data via Playwright."""
        try:
            loop = asyncio.get_event_loop()

            def fetch_with_playwright():
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(self.url, wait_until="networkidle", timeout=30000)
                    content = page.inner_text("body")
                    browser.close()
                    return content

            content = await loop.run_in_executor(None, fetch_with_playwright)

            last_updated = datetime.now().isoformat()

            self.groups = parse_outage_page(content)

            _LOGGER.info(f"Found {len(self.groups)} outage groups")

            return {
                "groups": self.groups,
                "last_updated": last_updated,
            }

        except Exception as e:
            _LOGGER.error(f"Error fetching data: {e}")
            return {}
