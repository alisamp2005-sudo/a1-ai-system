#!/bin/bash
# ============================================================
# А1 AI System — Запуск всех сервисов
# Одна команда для старта: ./scripts/start_all.sh
# ============================================================

set -e

# Цвета
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🏗  А1 AI System — Запуск всех сервисов"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd ~/a1-ai-system

# 1. Обновить код из GitHub
echo -e "${YELLOW}[1/6]${NC} Обновление кода из GitHub..."
git pull 2>/dev/null || echo "  ⚠️  git pull не удался (возможно есть локальные изменения)"
echo ""

# 2. Запустить Ollama (если не запущен)
echo -e "${YELLOW}[2/6]${NC} Проверка Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ Ollama уже запущен${NC}"
else
    echo "  Запускаю Ollama..."
    brew services start ollama 2>/dev/null || /opt/homebrew/opt/ollama/bin/ollama serve &
    sleep 3
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Ollama запущен${NC}"
    else
        echo -e "  ${RED}❌ Не удалось запустить Ollama${NC}"
    fi
fi
echo ""

# 3. Запустить Docker Compose
echo -e "${YELLOW}[3/6]${NC} Запуск Docker Compose (7 контейнеров)..."
docker compose up -d --build
echo -e "  ${GREEN}✅ Docker Compose запущен${NC}"
echo ""

# 4. Запустить Vision-сервис (в фоне)
echo -e "${YELLOW}[4/6]${NC} Запуск Vision-сервиса..."
# Проверяем, не занят ли порт
if lsof -i :11435 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ Vision-сервис уже запущен (порт 11435)${NC}"
else
    echo "  Запускаю vision_service.py в фоне..."
    nohup python3 scripts/vision_service.py > /tmp/vision_service.log 2>&1 &
    sleep 5
    if lsof -i :11435 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Vision-сервис запущен (порт 11435)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Vision-сервис не запустился (проверьте /tmp/vision_service.log)${NC}"
    fi
fi
echo ""

# 5. Запустить Whisper-сервис (в фоне)
echo -e "${YELLOW}[5/6]${NC} Запуск Whisper-сервиса..."
if lsof -i :11436 > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ Whisper-сервис уже запущен (порт 11436)${NC}"
else
    echo "  Запускаю whisper_service.py в фоне..."
    nohup python3 scripts/whisper_service.py > /tmp/whisper_service.log 2>&1 &
    sleep 10
    if lsof -i :11436 > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Whisper-сервис запущен (порт 11436)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Whisper-сервис ещё загружается (проверьте /tmp/whisper_service.log)${NC}"
    fi
fi
echo ""

# 6. Запустить Cloudflare Tunnel (в фоне)
echo -e "${YELLOW}[6/6]${NC} Запуск Cloudflare Tunnel..."
if pgrep -f "cloudflared tunnel run" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✅ Cloudflare Tunnel уже запущен${NC}"
else
    echo "  Запускаю tunnel..."
    nohup cloudflared tunnel --protocol http2 run a1-system > /tmp/cloudflared.log 2>&1 &
    sleep 3
    if pgrep -f "cloudflared tunnel run" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✅ Cloudflare Tunnel запущен (ai.bruceli.ru)${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Tunnel не запустился (проверьте /tmp/cloudflared.log)${NC}"
    fi
fi
echo ""

# Итог
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}🎉 Все сервисы запущены!${NC}"
echo ""
echo "  📱 Бот: @a1stroibot"
echo "  🌐 Dashboard: https://ai.bruceli.ru/dashboard"
echo "  ⚙️  Admin: https://ai.bruceli.ru/admin"
echo "  📋 Mini App: https://ai.bruceli.ru/miniapp/report"
echo ""
echo "  📊 Статус контейнеров:"
docker compose ps --format "table {{.Name}}\t{{.Status}}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
