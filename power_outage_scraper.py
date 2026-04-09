#!/usr/bin/env python3
"""
Script to scrape power outage information from https://poweron.loe.lviv.ua
and save it as JSON with ISO datetime format.
Uses Playwright to render JavaScript content.
"""

import re
import json
import logging
import argparse
import sys
import time
import yaml
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "Error: Playwright not installed. Run: pip install playwright && python3 -m playwright install chromium"
    )
    sys.exit(1)

from ha_rest_publisher import publish_to_ha

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML config file."""
    config_path = Path(path)
    if not config_path.exists():
        logger.error(f"Config file not found: {config_path.resolve()}")
        sys.exit(1)
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_page_content(url: str) -> str:
    """Fetch the webpage content using Playwright."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(1)
        content = page.inner_text("body")
        browser.close()
        return content


def extract_update_timestamp(text: str) -> str:
    """Extract the last update timestamp from the page text."""
    match = re.search(r"Інформація станом на (\d{1,2}:\d{2} \d{2}\.\d{2}\.\d{4})", text)
    if match:
        update_str = match.group(1)
        try:
            update_dt = datetime.strptime(update_str, "%H:%M %d.%m.%Y")
            return update_dt.isoformat()
        except ValueError:
            pass

    match = re.search(
        r"Дата та час оновлення діючих вимкненнь: (\w+), (\d+) (\w+) (\d+) р\. (\d{2}:\d{2}:\d{2})",
        text,
    )
    if match:
        day_name, day, month_name, year, time_str = match.groups()
        month_map = {
            "січня": "01",
            "лютого": "02",
            "березня": "03",
            "квітня": "04",
            "травня": "05",
            "червня": "06",
            "липня": "07",
            "серпня": "08",
            "вересня": "09",
            "жовтня": "10",
            "листопада": "11",
            "грудня": "12",
        }
        month = month_map.get(month_name.lower(), "01")
        try:
            update_dt = datetime.strptime(
                f"{year}-{month}-{day} {time_str}", "%Y-%m-%d %H:%M:%S"
            )
            return update_dt.isoformat()
        except ValueError:
            pass

    return datetime.now(timezone.utc).isoformat()


def extract_outage_info(text: str) -> list:
    """Extract outage group information from the page text."""
    outages = []

    date_pattern = r"Графік погодинних відключень на (\d{2}\.\d{2}\.\d{4})"
    date_matches = list(re.finditer(date_pattern, text))

    if not date_matches:
        logger.warning("Не знайдено заголовків з датами")
        return []

    date_sections = []
    for i, match in enumerate(date_matches):
        section_date = match.group(1)
        start_pos = match.end()
        end_pos = (
            date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
        )
        date_sections.append((section_date, text[start_pos:end_pos]))

    logger.info(f"Знайдено {len(date_sections)} секцій з датами")

    for section_date, section_text in date_sections:
        pattern = r"Група ([\d.]+)\. Електроенергії немає з (.+?)(?=\nГрупа|\Z)"
        matches = re.findall(pattern, section_text, re.DOTALL)

        for group, ranges_str in matches:
            existing_group = next((g for g in outages if g["group"] == group), None)

            if not existing_group:
                existing_group = {
                    "group": group,
                    "outages_today": [],
                    "outages_tomorrow": [],
                }
                outages.append(existing_group)

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
                    existing_group["outages_today"].extend(outage_ranges)
                else:
                    existing_group["outages_tomorrow"].extend(outage_ranges)

    return outages


def run_once(config: dict) -> bool:
    """Single scrape + save + publish cycle. Returns True on success."""
    url = config["scraper"]["url"]
    output_file = Path(config["scraper"]["json_output"])

    logger.info(f"🌐 Завантажую дані з {url}...")
    text_content = fetch_page_content(url)

    if not text_content:
        logger.error("Не вдалося отримати дані з сайту.")
        return False

    logger.info(f"Завантажено {len(text_content)} символів")

    last_updated = extract_update_timestamp(text_content)
    logger.info(f"Дані станом на: {last_updated}")

    outage_groups = extract_outage_info(text_content)

    if not outage_groups:
        logger.warning("⚠️  Жодної групи відключень не знайдено на сторінці.")

    result = {
        "last_updated": last_updated,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "outage_groups": outage_groups,
    }

    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Збережено: {output_file.resolve()}")
    except Exception as e:
        logger.error(f"Помилка збереження JSON: {e}")
        return False

    logger.info(f"Груп: {len(outage_groups)}")
    for g in outage_groups:
        today_periods = ", ".join(
            f"{o['start']}-{o['end']}" for o in g.get("outages_today", [])
        )
        tomorrow_periods = ", ".join(
            f"{o['start']}-{o['end']}" for o in g.get("outages_tomorrow", [])
        )
        logger.info(
            f"  Група {g['group']}: сьогодні: {today_periods or 'нема'}, завтра: {tomorrow_periods or 'нема'}"
        )

    publish_to_ha(config, result)

    return True


def run_daemon(config: dict):
    """Run scraper in a loop (daemon mode)."""
    interval = config["scraper"]["interval_minutes"] * 60
    logger.info(
        f"🔄 Daemon mode: оновлення кожні {config['scraper']['interval_minutes']} хв."
    )

    while True:
        try:
            run_once(config)
        except Exception as e:
            logger.exception(f"Неочікувана помилка: {e}")

        logger.info(
            f"💤 Наступна перевірка через {config['scraper']['interval_minutes']} хв."
        )
        time.sleep(interval)


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
