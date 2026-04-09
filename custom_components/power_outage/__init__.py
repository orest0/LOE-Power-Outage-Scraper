"""LOE Power Outage Scraper for Home Assistant."""

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import async_add_entities

from .const import DOMAIN, CONF_INTERVAL, CONF_URL
from .coordinator import PowerOutageCoordinator
from .sensor import (
    PowerOutageBinarySensor,
    PowerOutageNextSensor,
    PowerOutageTomorrowSensor,
    parse_outage_time,
)
from .calendar import PowerOutageCalendar

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LOE Power Outage from a config entry."""
    config = entry.data

    coordinator = PowerOutageCoordinator(hass, config)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    groups = coordinator.groups
    if groups:
        entities = []
        now = datetime.now()
        current_time = now.time()

        for group in groups:
            is_active = False
            current_outage = None
            next_outage = None

            for outage in group.outages_today:
                try:
                    t_start = parse_outage_time(outage["start"])
                    t_end = parse_outage_time(outage["end"])
                except ValueError:
                    continue

                if t_start <= current_time <= t_end:
                    is_active = True
                    current_outage = outage
                elif t_start > current_time and next_outage is None:
                    next_outage = outage

            entities.append(
                PowerOutageBinarySensor(
                    group.group_id,
                    is_active,
                    current_outage,
                    next_outage,
                    group.outages_today,
                )
            )

            entities.append(
                PowerOutageNextSensor(
                    group.group_id,
                    "start",
                    next_outage["start"] if next_outage else "—",
                )
            )

            entities.append(
                PowerOutageNextSensor(
                    group.group_id,
                    "end",
                    next_outage["end"] if next_outage else "—",
                )
            )

            if group.outages_tomorrow:
                entities.append(
                    PowerOutageTomorrowSensor(
                        group.group_id,
                        group.outages_today,
                        group.outages_tomorrow,
                    )
                )

            entities.append(
                PowerOutageCalendar(
                    group.group_id,
                    group.outages_today,
                    group.outages_tomorrow,
                )
            )

        await async_add_entities(entities)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
