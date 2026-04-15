# (В РОЗРОБЦІ) 🔌 LOE Power Outage Scraper - Home Assistant Integration

[![Open your Home Assistant instance and open the repository inside the HACS store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=orest0&repository=LOE-Power-Outage-Scraper&category=integration)

Ukrainian Power Outage Scraper Integration for Home Assistant. Automatically fetches power outage schedule from poweron.loe.lviv.ua and creates sensors and calendars in Home Assistant.

## 🇺🇦 Ukrainian / 🇬🇧 English

Ця інтеграція автоматично парсить графік відключень електроенергії з сайту LOE (Львівобленерго) і створює сенсори та календарі в Home Assistant.

This integration automatically scrapes power outage schedule from LOE (Lvivoblenergo) website and creates sensors and calendars in Home Assistant.

---

## 📦 Installation

### Option 1: HACS (Recommended)

1. Open Home Assistant
2. Go to **HACS** → **Integrations**
3. Click the **⋮** menu → **Custom repositories**
4. Add: `https://github.com/orest0/LOE-Power-Outage-Scraper`
5. Select category: **Integration**
6. Find "LOE Power Outage Scraper" and click **Install**

### Option 2: Manual

1. Copy `custom_components/power_outage/` folder to your Home Assistant config folder:
   ```
   /config/custom_components/power_outage/
   ```
2. Restart Home Assistant

---

## ⚙️ Configuration

### Step 1: Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "LOE Power Outage"
4. Configure:
   - **URL**: `https://poweron.loe.lviv.ua` (default)
   - **Update Interval**: 10 minutes (default)

### Step 2: Enjoy! 🎉

---

## 📱 Entities Created

### Global Sensors

| Entity ID | Description |
|-----------|-------------|
| `sensor.power_outage_last_updated` | Last data update time |
| `sensor.power_outage_active_groups` | Groups without power right now |

### Per Group Sensors

For each outage group (e.g., group `2.1` → suffix `2_1`):

| Entity ID | Description |
|-----------|-------------|
| `binary_sensor.power_outage_2_1` | `on` = outage active, `off` = power on |
| `sensor.power_outage_2_1_next_start` | Next outage start time |
| `sensor.power_outage_2_1_next_end` | Next outage end time |
| `sensor.power_outage_2_1_tomorrow` | First tomorrow outage start |
| `calendar.power_outage_2_1` | Calendar with all outages |

### Binary Sensor Attributes

- `schedule`: Today's schedule `["08:00–10:00", "16:00–18:00"]`
- `total_periods`: Number of outages today
- `current_outage_ends`: When current outage ends (if active)
- `next_outage_start` / `next_outage_end`: Next outage times
- `events`: All events (today + tomorrow)

### Tomorrow Sensor Attributes

- `schedule`: Tomorrow schedule
- `total_periods`: Number of outages tomorrow
- `events`: All events including today and tomorrow

---

## ⚡ Automation Examples

### Notify when outage starts

```yaml
automation:
  - alias: "Outage Started"
    trigger:
      - platform: state
        entity_id: binary_sensor.power_outage_2_1
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "⚡ Outage!"
          message: "Outage until {{ state_attr('binary_sensor.power_outage_2_1', 'current_outage_ends') }}"
```

### Notify 30 min before outage

```yaml
automation:
  - alias: "Warning Before Outage"
    trigger:
      - platform: template
        value_template: >
          {% set next = states('sensor.power_outage_2_1_next_start') %}
          {% if next != '—' %}
            {{ (strptime(next, '%H:%M').replace(year=now().year, month=now().month, day=now().day) - now()).total_seconds() | int == 1800 }}
          {% endif %}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "⚠️ Outage in 30 min!"
          message: "From {{ states('sensor.power_outage_2_1_next_start') }} to {{ states('sensor.power_outage_2_1_next_end') }}"
```

---

## 🔧 Troubleshooting

### No entities appear

- Check Home Assistant logs: **Settings** → **System** → **Logs**
- Make sure playwright is installed in HA: should be auto-installed via requirements
- Try restarting Home Assistant after adding the integration

### Calendar not showing events

- Make sure `local_calendar` integration is installed in Home Assistant
- Go to **Settings** → **Devices & Services** → **Add integration** → search "Local Calendar"

---

## 📋 Requirements

- Home Assistant 2024.1+
- Python 3.11+
- playwright
- pyyaml
- Internet connection to access poweron.loe.lviv.ua

---

## 📄 License

MIT License

## 🤝 Contributing

Pull requests are welcome! Please feel free to submit a Pull Request.
