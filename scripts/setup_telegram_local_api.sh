#!/usr/bin/env bash
# Configure Telegram Bot API Local Server without exposing credentials in chat or shell history.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$PROJECT_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  A1 AI System — Настройка локального Telegram API"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo

echo "Введите данные приложения из my.telegram.org → API development tools."
echo "API Hash не будет отображаться на экране и не попадёт в историю команд."
echo

read -r -p "Telegram API ID: " TELEGRAM_API_ID
if [[ ! "$TELEGRAM_API_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}Ошибка: API ID должен состоять только из цифр.${NC}"
    exit 1
fi

read -r -s -p "Telegram API Hash (ввод скрыт): " TELEGRAM_API_HASH
echo
if [[ -z "$TELEGRAM_API_HASH" ]]; then
    echo -e "${RED}Ошибка: API Hash не может быть пустым.${NC}"
    exit 1
fi

DEFAULT_LOCAL_URL="http://telegram_bot_api:8081"
read -r -p "Адрес локального API [$DEFAULT_LOCAL_URL]: " TELEGRAM_LOCAL_API_URL
TELEGRAM_LOCAL_API_URL="${TELEGRAM_LOCAL_API_URL:-$DEFAULT_LOCAL_URL}"

# The .env file contains secrets; restrict it to the current Mac user.
touch "$ENV_FILE"
chmod 600 "$ENV_FILE"

upsert_env() {
    local key="$1"
    local value="$2"
    local temp_file
    temp_file="$(mktemp)"

    awk -v key="$key" -v value="$value" '
        index($0, key "=") == 1 {
            if (!replaced) {
                print key "=" value
                replaced = 1
            }
            next
        }
        { print }
        END {
            if (!replaced) print key "=" value
        }
    ' "$ENV_FILE" > "$temp_file"

    mv "$temp_file" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
}

upsert_env "TELEGRAM_API_ID" "$TELEGRAM_API_ID"
upsert_env "TELEGRAM_API_HASH" "$TELEGRAM_API_HASH"
upsert_env "TELEGRAM_LOCAL_API_URL" "$TELEGRAM_LOCAL_API_URL"

echo
echo -e "${GREEN}✅ Данные сохранены в .env.${NC}"
echo "   API ID: задан"
echo "   API Hash: задан"
echo "   Local API URL: $TELEGRAM_LOCAL_API_URL"
echo

echo "Перезапускаю локальный Telegram API и бота..."
docker compose up -d --force-recreate telegram_bot_api telegram_bot
sleep 5

echo
echo "Проверка запуска:"
docker compose logs telegram_bot --tail 20 | grep -E "Using LOCAL Telegram Bot API|Bot is starting|Run polling" || true

echo
echo -e "${GREEN}Готово.${NC} Отправьте боту короткое сообщение и затем повторите запрос:"
echo "  Покажи Реестр контрактов 2026"
