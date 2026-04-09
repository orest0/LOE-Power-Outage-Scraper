"""Sensor platform for LOE Power Outage."""

from datetime import datetime, timedelta
import logging
import re

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_GROUPS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Set up sensors from config entry."""
    from .coordinator import PowerOutageCoordinator

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

        is_active = False
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
                not no_power,  # Inverted: ON = power available
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

    if entities:
        async_add_entities(entities)
        _LOGGER.info(f"Added {len(entities)} sensor entities")


def parse_outage_time(t_str: str):
    """Parse HH:MM string to time."""
    return datetime.strptime(t_str, "%H:%M").time()


class PowerOutageGroup:
    """Represents a power outage group."""

    def __init__(self, group_id: str):
        self.group_id = group_id
        self.suffix = group_id.replace(".", "_")
        self.outages_today = []
        self.outages_tomorrow = []


def parse_outage_page(text: str) -> list[PowerOutageGroup]:
    """Parse outage information from page text."""
    groups = []

    date_pattern = r"Графік погодинних відключень на (\d{2}\.\d{2}\.\d{4})"
    date_matches = list(re.finditer(date_pattern, text))

    if not date_matches:
        return []

    date_sections = []
    for i, match in enumerate(date_matches):
        section_date = match.group(1)
        start_pos = match.end()
        end_pos = (
            date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
        )
        date_sections.append((section_date, text[start_pos:end_pos]))

    for section_date, section_text in date_sections:
        pattern = r"Група ([\d.]+)\. Електроенергії немає з (.+?)(?=\nГрупа|\Z)"
        matches = re.findall(pattern, section_text, re.DOTALL)

        for group, ranges_str in matches:
            existing_group = next((g for g in groups if g.group_id == group), None)

            if not existing_group:
                existing_group = PowerOutageGroup(group)
                groups.append(existing_group)

            ranges_str = ranges_str.strip()
            range_parts = re.split(r",\s*з\s*", ranges_str)

            outage_ranges = []
            for range_part in range_parts:
                range_part = range_part.strip()
                match = re.search(r"(\d{1,2}:\d{2})\s*до\s*(\d{1,2}:\d{2})", range_part)
                if match:
                    outage_ranges.append(
                        {"start": match.group(1), "end": match.group(2)}
                    )

            if outage_ranges:
                today = datetime.now().strftime("%d.%m.%Y")
                if section_date == today:
                    existing_group.outages_today.extend(outage_ranges)
                else:
                    existing_group.outages_tomorrow.extend(outage_ranges)

    return groups


class PowerOutageBinarySensor(BinarySensorEntity):
    """Binary sensor for power outage status."""

    def __init__(
        self,
        group_id: str,
        is_active: bool,
        current_outage: dict | None,
        next_outage: dict | None,
        outages: list,
    ):
        self._group_id = group_id
        self._attr_unique_id = f"power_outage_{group_id.replace('.', '_')}"
        self._attr_name = f"Power Outage {group_id}"
        self._attr_is_on = is_active
        self._attr_icon = "mdi:power-plug" if is_active else "mdi:power-plug-off"
        self._attr_device_class = "power"

        schedule = [f"{o['start']}–{o['end']}" for o in outages]
        self._attr_extra_state_attributes = {
            "schedule": schedule,
            "total_periods": len(outages),
            "group": group_id,
            "power_available": is_active,
        }

        if not is_active and current_outage:
            self._attr_extra_state_attributes["current_outage_ends"] = current_outage[
                "end"
            ]

        if next_outage:
            self._attr_extra_state_attributes["next_outage_start"] = next_outage[
                "start"
            ]
            self._attr_extra_state_attributes["next_outage_end"] = next_outage["end"]
        else:
            self._attr_extra_state_attributes["next_outage_start"] = "—"
            self._attr_extra_state_attributes["next_outage_end"] = "—"


class PowerOutageNextSensor(SensorEntity):
    """Sensor for next outage start/end time."""

    def __init__(self, group_id: str, sensor_type: str, value: str):
        self._group_id = group_id
        self._sensor_type = sensor_type
        self._attr_unique_id = (
            f"power_outage_{group_id.replace('.', '_')}_next_{sensor_type}"
        )
        self._attr_name = f"Power Outage {group_id} Next {sensor_type.capitalize()}"
        self._attr_state = value
        self._attr_icon = (
            "mdi:clock-alert-outline"
            if sensor_type == "start"
            else "mdi:clock-check-outline"
        )


class PowerOutageTomorrowSensor(SensorEntity):
    """Sensor for tomorrow's outages."""

    def __init__(
        self,
        group_id: str,
        outages_today: list,
        outages_tomorrow: list,
    ):
        self._group_id = group_id
        self._attr_unique_id = f"power_outage_{group_id.replace('.', '_')}_tomorrow"
        self._attr_name = f"Power Outage {group_id} Tomorrow"

        if outages_tomorrow:
            self._attr_state = outages_tomorrow[0]["start"]
            self._attr_icon = "mdi:calendar-tomorrow"
            schedule = [f"{o['start']}–{o['end']}" for o in outages_tomorrow]

            all_events = []
            today = datetime.now().strftime("%Y-%m-%d")
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

            for outage in outages_today:
                all_events.append(
                    {
                        "start": outage["start"],
                        "end": outage["end"],
                        "date": today,
                    }
                )

            for outage in outages_tomorrow:
                all_events.append(
                    {
                        "start": outage["start"],
                        "end": outage["end"],
                        "date": tomorrow,
                    }
                )

            self._attr_extra_state_attributes = {
                "schedule": schedule,
                "total_periods": len(outages_tomorrow),
                "next_start": outages_tomorrow[0]["start"],
                "next_end": outages_tomorrow[0]["end"],
                "events": all_events,
            }
        else:
            self._attr_state = "—"
            self._attr_icon = "mdi:calendar-check"
            self._attr_extra_state_attributes = {
                "schedule": [],
                "total_periods": 0,
                "next_start": "—",
                "next_end": "—",
                "events": [],
            }
