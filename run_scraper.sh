#!/bin/bash
# Run LOE Power Outage Scraper
cd /home/pi/power_outages
python3 -c "from scraper.parser import run_scraper; run_scraper()"