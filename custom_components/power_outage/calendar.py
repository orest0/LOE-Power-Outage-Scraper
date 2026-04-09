"""Calendar platform for LOE Power Outage."""

from datetime import datetime, timedelta
import logging
import re
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sensor import parse_outage_page, PowerOutageGroup

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up calendar from config entry."""
    pass


def create_calendar_entities(groups: list[PowerOutageGroup]) -> list:
    """Create calendar entities from groups."""
    entities = []

    for group in groups:
        entities.append(
            PowerOutageCalendar(
                group.group_id, group.outages_today, group.outages_tomorrow
            )
        )

    return entities


class PowerOutageCalendar(CalendarEntity):
    """Calendar entity for power outage group."""

    def __init__(self, group_id: str, outages_today: list, outages_tomorrow: list):
        self._group_id = group_id
        self._suffix = group_id.replace(".", "_")
        self._outages_today = outages_today
        self._outages_tomorrow = outages_tomorrow
        self._attr_unique_id = f"power_outage_{self._suffix}"
        self._attr_name = f"Power Outage {group_id}"
        self._attr_icon = "mdi:calendar-clock"

    def _get_events(self) -> list[CalendarEvent]:
        """Get all calendar events."""
        events = []
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        for outage in self._outages_today:
            start_time = outage["start"]
            end_time = outage["end"]

            if end_time == "24:00":
                end_time = "23:59"

            try:
                start = datetime.strptime(f"{today_str} {start_time}", "%Y-%m-%d %H:%M")
                end = datetime.strptime(f"{today_str} {end_time}", "%Y-%m-%d %H:%M")

                events.append(
                    CalendarEvent(
                        summary=f"Відключення {self._group_id}",
                        start=start,
                        end=end,
                        description=f"Сьогодні {start_time}-{end_time}",
                    )
                )
            except ValueError:
                pass

        for outage in self._outages_tomorrow:
            start_time = outage["start"]
            end_time = outage["end"]

            if end_time == "24:00":
                end_time = "23:59"

            try:
                start = datetime.strptime(
                    f"{tomorrow_str} {start_time}", "%Y-%m-%d %H:%M"
                )
                end = datetime.strptime(f"{tomorrow_str} {end_time}", "%Y-%m-%d %H:%M")

                events.append(
                    CalendarEvent(
                        summary=f"Відключення {self._group_id}",
                        start=start,
                        end=end,
                        description=f"Завтра {start_time}-{end_time}",
                    )
                )
            except ValueError:
                pass

        return events

    async def async_get_events(
        self, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get events within a date range."""
        all_events = self._get_events()
        return [e for e in all_events if start_date <= e.start < end_date]

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        now = datetime.now()
        events = self._get_events()

        upcoming = [e for e in events if e.start >= now]
        if upcoming:
            upcoming.sort(key=lambda e: e.start)
            return upcoming[0]

        return None
