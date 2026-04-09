# 🔌 LOE Power Outage Scraper → Home Assistant

Скрипт автоматично парсить графік відключень з [poweron.loe.lviv.ua](https://poweron.loe.lviv.ua) і публікує дані в Home Assistant через REST API.

---

## 📁 Файли проекту

| Файл | Призначення |
|------|-------------|
| `power_outage_scraper.py` | Головний скрипт (парсер + daemon loop) |
| `ha_rest_publisher.py` | Публікація даних в HA через REST API |
| `config.yaml` | Всі налаштування |
| `power-outage.service` | Systemd сервіс для RPi5 |
| `setup.sh` | Автоматичне налаштування на RPi5 |

---

## 🚀 Деплой на Raspberry Pi 5

### Крок 1 — Клонуй репозиторій на RPi

Підключись до RPi по SSH і виконай:
```bash
git clone git@github.com:orest0/LOE-Power-Outage-Scraper.git ~/power_outages
cd ~/power_outages
```

### Крок 2 — Отримай HA Long-Lived Access Token

1. Відкрий Home Assistant
2. Натисни на **своє ім'я** (ліворуч знизу)
3. Прокрути вниз → **Long-Lived Access Tokens**
4. Натисни **Create Token**, дай йому назву `power-outage`
5. **Скопіюй токен** (він показується лише один раз!)

### Крок 3 — Налаштуй config.yaml

```bash
nano ~/power_outages/config.yaml
```

Вставте свій токен:
```yaml
home_assistant:
  url: "http://localhost:8123"
  token: "eyJ0eXAiOiJKV1..."   # ← вставити сюди

scraper:
  url: "https://poweron.loe.lviv.ua"
  interval_minutes: 30
  json_output: "power_outages.json"
```

### Крок 4 — Тест (один запуск)

```bash
cd ~/power_outages
pip3 install requests pyyaml
python3 power_outage_scraper.py --once
```

Ти повинен побачити щось на кшталт:
```
2026-04-09 16:00:00 [INFO] 🌐 Завантажую дані з https://poweron.loe.lviv.ua...
2026-04-09 16:00:01 [INFO] Знайдено 12 груп відключень
2026-04-09 16:00:01 [INFO] 💾 Збережено: power_outages.json
2026-04-09 16:00:01 [INFO] 📡 Публікую 12 груп в HA...
2026-04-09 16:00:02 [INFO] ✅ Опубліковано 38 сутностей в HA
```

### Крок 5 — Встановлення як системний сервіс

```bash
cd ~/power_outages
sudo bash setup.sh
```

Скрипт сам:
- встановить залежності
- налаштує сервіс під твого користувача
- увімкне автозапуск при старті RPi

---

## 🏠 Що з'явиться в Home Assistant

Після першого запуску в **Developer Tools → States** з'являться:

### Глобальні сенсори
| Entity ID | Опис |
|-----------|------|
| `sensor.power_outage_last_updated` | Час оновлення даних з LOE |
| `sensor.power_outage_active_groups` | Групи без світла прямо зараз |

### Для кожної групи (напр. група `2.1` → суфікс `2_1`)
| Entity ID | Опис |
|-----------|------|
| `binary_sensor.power_outage_2_1` | `on` = відключення зараз, `off` = світло є |
| `sensor.power_outage_2_1_next_start` | Коли почнеться наступне відключення |
| `sensor.power_outage_2_1_next_end` | Коли закінчиться |

У **атрибутах** `binary_sensor.power_outage_2_1`:
- `schedule` — весь графік дня: `["08:00–10:00", "16:00–18:00"]`
- `total_periods` — кількість відключень сьогодні
- `current_outage_ends` — коли закінчиться поточне (якщо активне)
- `next_outage_start` / `next_outage_end` — наступне

---

## ⚡ Приклади автоматизацій в HA

### Сповіщення коли починається відключення
```yaml
automation:
  - alias: "Почалось відключення"
    trigger:
      - platform: state
        entity_id: binary_sensor.power_outage_2_1   # ← заміни на свою групу
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: "⚡ Відключення!"
          message: >
            Відключення до {{ state_attr('binary_sensor.power_outage_2_1', 'current_outage_ends') }}
```

### Сповіщення за 30 хв до відключення
```yaml
automation:
  - alias: "Попередження про відключення"
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
          title: "⚠️ Через 30 хв відключення!"
          message: "З {{ states('sensor.power_outage_2_1_next_start') }} до {{ states('sensor.power_outage_2_1_next_end') }}"
```

### Увімкнути зарядку повербанку коли є світло
```yaml
automation:
  - alias: "Зарядка при наявності світла"
    trigger:
      - platform: state
        entity_id: binary_sensor.power_outage_2_1
        to: "off"
    action:
      - service: switch.turn_on
        entity_id: switch.powerbank_charger
```

---

## 🔧 Керування сервісом на RPi

```bash
# Перевірити статус
sudo systemctl status power-outage

# Подивитись логи в реальному часі
journalctl -u power-outage -f

# Перезапустити
sudo systemctl restart power-outage

# Зупинити
sudo systemctl stop power-outage
```

---

## ❓ Troubleshooting

**`HTTP 401 Unauthorized`** — невірний або прострочений токен в `config.yaml`

**`Connection refused`** — HA не запущений або невірна URL в config

**Сенсори не з'являються в HA** — перевір логи: `journalctl -u power-outage -n 50`

**Жодної групи не знайдено** — можливо сайт LOE змінив HTML структуру; перевір вручну: `python3 power_outage_scraper.py --once`
