"""Scraper module for parsing power outage data from poweron.loe.lviv.ua."""

import re
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "Error: Playwright not installed. Run: pip install playwright && python3 -m playwright install chromium"
    )
    sync_playwright = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_URL = "https://poweron.loe.lviv.ua"
DEFAULT_JSON_PATH = "/home/pi/power_outages/data/outages.json"


def load_config() -> dict:
    """Load configuration."""
    return {
        "url": DEFAULT_URL,
        "json_file": DEFAULT_JSON_PATH,
    }


def fetch_page_content(url: str) -> Optional[str]:
    """Fetch the webpage content using Playwright."""
    if sync_playwright is None:
        logger.error("Playwright not available")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=30000)
            import time

            time.sleep(1)
            content = page.inner_text("body")
            browser.close()
            return content
    except Exception as e:
        logger.error(f"Error fetching page: {e}")
        return None


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
            "серпеня": "08",
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

    return datetime.now().isoformat()


def parse_outage_groups(text: str) -> list[dict]:
    """Parse outage groups from page text, separating today and tomorrow."""
    groups = []

    date_pattern = r"Графік погодинних відключень на (\d{2}\.\d{2}\.\d{4})"
    date_matches = list(re.finditer(date_pattern, text))

    if not date_matches:
        logger.warning("No date headers found in page")
        return []

    date_sections = []
    for i, match in enumerate(date_matches):
        section_date = match.group(1)
        start_pos = match.end()
        end_pos = (
            date_matches[i + 1].start() if i + 1 < len(date_matches) else len(text)
        )
        date_sections.append((section_date, text[start_pos:end_pos]))

    logger.info(f"Found {len(date_sections)} date sections")

    for section_date, section_text in date_sections:
        pattern = r"Група ([\d.]+)\. Електроенергії немає з (.+?)(?=\nГрупа|\Z)"
        matches = re.findall(pattern, section_text, re.DOTALL)

        for group, ranges_str in matches:
            existing_group = next((g for g in groups if g["group"] == group), None)

            if not existing_group:
                existing_group = {
                    "group": group,
                    "outages_today": [],
                    "outages_tomorrow": [],
                }
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
                    existing_group["outages_today"].extend(outage_ranges)
                else:
                    existing_group["outages_tomorrow"].extend(outage_ranges)

    return groups


def save_outages(data: dict, filepath: str) -> None:
    """Save outage data to JSON file."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_scraper() -> Optional[dict]:
    """Run the scraper and return parsed data."""
    config = load_config()

    logger.info(f"Fetching data from {config['url']}...")
    text_content = fetch_page_content(config["url"])

    if not text_content:
        logger.error("Failed to fetch page content")
        return None

    logger.info(f"Downloaded {len(text_content)} characters")

    last_updated = extract_update_timestamp(text_content)
    outage_groups = parse_outage_groups(text_content)

    result = {
        "last_updated": last_updated,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "outage_groups": outage_groups,
    }

    save_outages(result, config["json_file"])
    logger.info(f"Saved to {config['json_file']}")

    for g in outage_groups:
        today = ", ".join(
            f"{o['start']}-{o['end']}" for o in g.get("outages_today", [])
        )
        tomorrow = ", ".join(
            f"{o['start']}-{o['end']}" for o in g.get("outages_tomorrow", [])
        )
        logger.info(
            f"  Group {g['group']}: today={today or 'none'}, tomorrow={tomorrow or 'none'}"
        )

    return result


if __name__ == "__main__":
    run_scraper()
