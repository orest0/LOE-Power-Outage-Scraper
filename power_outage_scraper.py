#!/usr/bin/env python3
"""
Script to scrape power outage information from https://poweron.loe.lviv.ua
and save it as JSON with ISO datetime format.
Publishes data to Home Assistant via REST API.
Works without BeautifulSoup using only regex and requests.
"""

import re
import json
import logging
import argparse
import sys
import time
import yaml
import requests
from datetime import datetime
from pathlib import Path

from ha_rest_publisher import publish_to_ha

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Config ───────────────────────────────────────────────────────────────────

def load_config(path: str = "config.yaml") -> dict:
    """Load YAML config file."""
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path.resolve()}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Scraper functions (original, unchanged) ───────────────────────────────────

def fetch_page_content(url):
    """Fetch the webpage content."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching page: {e}")
        return None


def extract_update_timestamp(text):
    """Extract the last update timestamp from the page text."""
    match = re.search(
        r'\*\*Інформація станом на (\d{1,2}:\d{2} \d{2}\.\d{2}\.\d{4})\*\*', text
    )
    if match:
        update_str = match.group(1)
        try:
            update_dt = datetime.strptime(update_str, '%H:%M %d.%m.%Y')
            return update_dt.isoformat()
        except ValueError:
            pass

    match = re.search(
        r'— Дата та час оновлення діючих вимкненнь: (\w+), (\d+) (\w+) (\d+) р\. (\d{2}:\d{2}:\d{2})',
        text,
    )
    if match:
        day_name, day, month_name, year, time_str = match.groups()
        month_map = {
            'січня': '01', 'лютого': '02', 'березня': '03', 'квітня': '04',
            'травня': '05', 'червня': '06', 'липня': '07', 'серпня': '08',
            'вересня': '09', 'жовтня': '10', 'листопада': '11', 'грудня': '12',
        }
        month = month_map.get(month_name.lower(), '01')
        try:
            update_dt = datetime.strptime(f'{year}-{month}-{day} {time_str}', '%Y-%m-%d %H:%M:%S')
            return update_dt.isoformat()
        except ValueError:
            pass

    return datetime.now().isoformat()


def extract_outage_info(text):
    """Extract outage group information from the page text."""
    outages = []

    section_pattern = (
        r'\*\*Графік погодинних відключень на \d{2}\.\d{2}\.\d{4}\*\*'
        r'[\s\S]*?(?=\*\*|\n\n\n|\Z)'
    )
    section_match = re.search(section_pattern, text)
    section_text = section_match.group(0) if section_match else text

    outage_pattern = (
        r'Група (\d+\.\d+)\. Електроенергії немає з '
        r'((?:\d{2}:\d{2} до \d{2}:\d{2}(?:, з \d{2}:\d{2} до \d{2}:\d{2})*))'
    )
    matches = re.findall(outage_pattern, section_text)
    logger.info(f"Знайдено {len(matches)} груп відключень")

    for group, ranges_str in matches:
        ranges = [r.strip() for r in ranges_str.split(', з ')]
        if ranges[0].startswith('з '):
            ranges[0] = ranges[0][2:]

        outage_ranges = []
        for range_str in ranges:
            if ' до ' in range_str:
                start_str, end_str = range_str.split(' до ')
                outage_ranges.append({
                    'start': start_str.strip(),
                    'end': end_str.strip(),
                })

        outages.append({'group': group, 'outages': outage_ranges})

    return outages


# ── Main run logic ────────────────────────────────────────────────────────────

def run_once(config: dict) -> bool:
    """
    Single scrape + save + publish cycle.
    Returns True on success.
    """
    url = config["scraper"]["url"]
    output_file = Path(config["scraper"]["json_output"])

    logger.info(f"🌐 Завантажую дані з {url}...")
    html_content = fetch_page_content(url)

    if not html_content:
        logger.error("Не вдалося отримати дані з сайту.")
        return False

    logger.info(f"Завантажено {len(html_content)} символів")

    last_updated = extract_update_timestamp(html_content)
    logger.info(f"Дані станом на: {last_updated}")

    outage_groups = extract_outage_info(html_content)

    if not outage_groups:
        logger.warning("⚠️  Жодної групи відключень не знайдено на сторінці.")

    result = {
        "last_updated": last_updated,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "outage_groups": outage_groups,
    }

    # Зберегти JSON
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Збережено: {output_file.resolve()}")
    except Exception as e:
        logger.error(f"Помилка збереження JSON: {e}")
        return False

    # Надрукувати підсумок
    logger.info(f"Груп: {len(outage_groups)}")
    for g in outage_groups:
        periods = ", ".join(f"{o['start']}–{o['end']}" for o in g["outages"])
        logger.info(f"  Група {g['group']}: {periods or 'нема'}")

    # Опублікувати в HA
    publish_to_ha(config, result)

    return True


def run_daemon(config: dict):
    """Run scraper in a loop (daemon mode)."""
    interval = config["scraper"]["interval_minutes"] * 60
    logger.info(f"🔄 Daemon mode: оновлення кожні {config['scraper']['interval_minutes']} хв.")

    while True:
        try:
            run_once(config)
        except Exception as e:
            logger.exception(f"Неочікувана помилка: {e}")

        logger.info(f"💤 Наступна перевірка через {config['scraper']['interval_minutes']} хв.")
        time.sleep(interval)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Скрапер відключень LOE → Home Assistant"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Виконати один раз і вийти (за замовчуванням — daemon mode)",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Шлях до конфіг файлу (за замовчуванням: config.yaml)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.once:
        success = run_once(config)
        sys.exit(0 if success else 1)
    else:
        run_daemon(config)


if __name__ == "__main__":
    main()