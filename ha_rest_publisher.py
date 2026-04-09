#!/usr/bin/env python3
"""
Home Assistant REST API publisher for power outage data.
Publishes ALL found outage groups as separate sensors/binary_sensors.
"""

import json
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


def _post_state(ha_url: str, headers: dict, entity_id: str, state: str, attributes: dict) -> bool:
    """POST a single entity state to HA REST API."""
    url = f"{ha_url}/api/states/{entity_id}"
    payload = {"state": state, "attributes": attributes}
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            logger.debug(f"  ✓ {entity_id} = {state}")
            return True
        else:
            logger.error(f"  ✗ {entity_id}: HTTP {resp.status_code} – {resp.text[:100]}")
            return False
    except requests.RequestException as e:
        logger.error(f"  ✗ {entity_id}: {e}")
        return False


def _parse_time(t_str: str):
    """Parse HH:MM string to datetime.time object."""
    return datetime.strptime(t_str, "%H:%M").time()


def publish_to_ha(config: dict, data: dict) -> int:
    """
    Publish all outage groups to Home Assistant via REST API.
    Returns count of successfully updated entities.
    """
    ha_url = config["home_assistant"]["url"].rstrip("/")
    token = config["home_assistant"]["token"]

    if token == "PASTE_YOUR_TOKEN_HERE":
        logger.error("❌ HA token not configured in config.yaml!")
        return 0

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    now = datetime.now()
    current_time = now.time()
    groups = data.get("outage_groups", [])
    last_updated = data.get("last_updated", now.isoformat())
    date = data.get("date", now.strftime("%Y-%m-%d"))

    logger.info(f"📡 Публікую {len(groups)} груп в HA...")
    ok_count = 0

    # ── Глобальний сенсор: час оновлення ──────────────────────────────────
    if _post_state(ha_url, headers,
                   "sensor.power_outage_last_updated",
                   last_updated[:16].replace("T", " "),
                   {
                       "friendly_name": "Відключення: оновлено",
                       "icon": "mdi:update",
                       "date": date,
                       "groups_count": len(groups),
                   }):
        ok_count += 1

    # ── Глобальний сенсор: список груп без світла зараз ────────────────────
    active_now = []
    for gd in groups:
        for outage in gd.get("outages", []):
            try:
                if _parse_time(outage["start"]) <= current_time <= _parse_time(outage["end"]):
                    active_now.append(gd["group"])
                    break
            except ValueError:
                pass

    if _post_state(ha_url, headers,
                   "sensor.power_outage_active_groups",
                   ", ".join(active_now) if active_now else "немає",
                   {
                       "friendly_name": "Відключення: активні групи",
                       "icon": "mdi:transmission-tower-off" if active_now else "mdi:transmission-tower",
                       "count": len(active_now),
                   }):
        ok_count += 1

    # ── Сенсори для кожної групи ──────────────────────────────────────────
    for group_data in groups:
        group_id = group_data["group"]          # e.g. "1.1"
        suffix = group_id.replace(".", "_")      # e.g. "1_1"
        outages = group_data.get("outages", [])

        # Визначити поточний/наступний відрізок відключення
        is_active = False
        current_outage = None
        next_outage = None

        for outage in outages:
            try:
                t_start = _parse_time(outage["start"])
                t_end = _parse_time(outage["end"])
            except ValueError:
                continue

            if t_start <= current_time <= t_end:
                is_active = True
                current_outage = outage
            elif t_start > current_time and next_outage is None:
                next_outage = outage

        # Форматований розклад для атрибутів
        schedule_str = [f"{o['start']}–{o['end']}" for o in outages]

        # Спільні атрибути групи
        group_attrs = {
            "friendly_name": f"Відключення: група {group_id}",
            "device_class": "problem",
            "icon": "mdi:power-plug-off" if is_active else "mdi:power-plug",
            "schedule": schedule_str,
            "total_periods": len(outages),
            "group": group_id,
        }

        if is_active and current_outage:
            group_attrs["current_outage_ends"] = current_outage["end"]
        if next_outage:
            group_attrs["next_outage_start"] = next_outage["start"]
            group_attrs["next_outage_end"] = next_outage["end"]
        else:
            group_attrs["next_outage_start"] = "—"
            group_attrs["next_outage_end"] = "—"

        # binary_sensor — є відключення зараз?
        if _post_state(ha_url, headers,
                       f"binary_sensor.power_outage_{suffix}",
                       "on" if is_active else "off",
                       group_attrs):
            ok_count += 1

        # sensor — коли наступне відключення починається
        if _post_state(ha_url, headers,
                       f"sensor.power_outage_{suffix}_next_start",
                       next_outage["start"] if next_outage else "—",
                       {
                           "friendly_name": f"Група {group_id}: наступне від",
                           "icon": "mdi:clock-alert-outline",
                       }):
            ok_count += 1

        # sensor — коли наступне відключення закінчується
        if _post_state(ha_url, headers,
                       f"sensor.power_outage_{suffix}_next_end",
                       next_outage["end"] if next_outage else "—",
                       {
                           "friendly_name": f"Група {group_id}: наступне до",
                           "icon": "mdi:clock-check-outline",
                       }):
            ok_count += 1

    logger.info(f"✅ Опубліковано {ok_count} сутностей в HA")
    return ok_count
