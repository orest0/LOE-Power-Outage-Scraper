#!/bin/bash
# setup.sh — Налаштування Power Outage Scraper на Raspberry Pi
# Запускати: bash setup.sh
set -e

# ── Кольори ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ── Перевірки ────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Запускай від root: sudo bash setup.sh"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTUAL_USER="${SUDO_USER:-$USER}"
SERVICE_NAME="power-outage"

info "Директорія скрипта: $SCRIPT_DIR"
info "Користувач: $ACTUAL_USER"

# ── Залежності ───────────────────────────────────────────────────────────────
info "Встановлення Python залежностей..."
pip3 install --quiet requests pyyaml
info "✅ requests, pyyaml встановлено"

# ── Оновлення service файлу ───────────────────────────────────────────────────
SERVICE_FILE="$SCRIPT_DIR/$SERVICE_NAME.service"
if [[ ! -f "$SERVICE_FILE" ]]; then
    error "Файл $SERVICE_FILE не знайдено!"
fi

# Замінюємо YOUR_USERNAME на реального користувача
sed -i "s/YOUR_USERNAME/$ACTUAL_USER/g" "$SERVICE_FILE"
# Замінюємо шлях, якщо скрипт не в /home/user/power_outages
sed -i "s|/home/$ACTUAL_USER/power_outages|$SCRIPT_DIR|g" "$SERVICE_FILE"
info "✅ Service файл оновлено під користувача $ACTUAL_USER"

# ── Копіюємо service файл ─────────────────────────────────────────────────────
cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
info "✅ Service файл скопійовано в /etc/systemd/system/"

# ── Перевірка config.yaml ────────────────────────────────────────────────────
CONFIG_FILE="$SCRIPT_DIR/config.yaml"
if [[ ! -f "$CONFIG_FILE" ]]; then
    error "config.yaml не знайдено! Скопіюй всі файли проекту на RPi."
fi

if grep -q "PASTE_YOUR_TOKEN_HERE" "$CONFIG_FILE"; then
    warning "⚠️  Не забудь вставити HA токен в config.yaml!"
    warning "   Settings → Profile → Long-Lived Access Tokens → Create Token"
fi

# ── Активуємо сервіс ─────────────────────────────────────────────────────────
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
info "✅ Сервіс увімкнено (стартує при завантаженні)"

# ── Запитуємо чи запустити зараз ─────────────────────────────────────────────
echo ""
read -p "$(echo -e ${YELLOW})Запустити сервіс зараз? [y/N]: $(echo -e ${NC})" yn
if [[ "$yn" =~ ^[Yy]$ ]]; then
    systemctl start "$SERVICE_NAME"
    sleep 2
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        info "✅ Сервіс запущено!"
        info "Логи: journalctl -u $SERVICE_NAME -f"
    else
        error "Сервіс не запустився. Дивись: journalctl -u $SERVICE_NAME -n 30"
    fi
else
    info "Запустиш пізніше: sudo systemctl start $SERVICE_NAME"
fi

echo ""
info "═══════════════════════════════════════════"
info "  Налаштування завершено!"
info "  Керування сервісом:"
info "    Статус:  sudo systemctl status $SERVICE_NAME"
info "    Логи:    journalctl -u $SERVICE_NAME -f"
info "    Стоп:    sudo systemctl stop $SERVICE_NAME"
info "    Старт:   sudo systemctl start $SERVICE_NAME"
info "═══════════════════════════════════════════"
