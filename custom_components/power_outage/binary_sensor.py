"""Binary sensor platform for LOE Power Outage."""

import logging

from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_GROUPS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up binary sensors from config entry."""
    from .coordinator import PowerOutageCoordinator
    from .sensor import PowerOutageBinarySensor, parse_outage_time
    from datetime import datetime

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if not coordinator:
        _LOGGER.error("Coordinator not found")
        return

    groups = coordinator.groups
    selected_groups = entry.data.get(CONF_GROUPS, [])
    now = datetime.now()
    current_time = now.time()

    entities = []
    for group in groups:
        if selected_groups and group.group_id not in selected_groups:
            continue

        no_power = False
        current_outage = None
        next_outage = None

        for outage in group.outages_today:
            try:
                t_start = parse_outage_time(outage["start"])
                t_end = parse_outage_time(outage["end"])
            except ValueError:
                continue

            if t_start <= current_time <= t_end:
                no_power = True
                current_outage = outage
            elif t_start > current_time and next_outage is None:
                next_outage = outage

        entities.append(
            PowerOutageBinarySensor(
                group.group_id,
                not no_power,
                current_outage,
                next_outage,
                group.outages_today,
            )
        )

    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"Added {len(entities)} binary sensor entities")
