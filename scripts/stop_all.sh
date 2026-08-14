#!/bin/bash
# ============================================================
# А1 AI System — Остановка всех сервисов
# Одна команда для остановки: ./scripts/stop_all.sh
# ============================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🛑 А1 AI System — Остановка всех сервисов"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd ~/a1-ai-system

# 1. Остановить Cloudflare Tunnel
echo "[1/4] Остановка Cloudflare Tunnel..."
pkill -f "cloudflared tunnel run" 2>/dev/null && echo "  ✅ Tunnel остановлен" || echo "  — Tunnel не был запущен"

# 2. Остановить Vision-сервис
echo "[2/4] Остановка Vision-сервиса..."
pkill -f "vision_service.py" 2>/dev/null && echo "  ✅ Vision остановлен" || echo "  — Vision не был запущен"

# 3. Остановить Docker Compose
echo "[3/4] Остановка Docker Compose..."
docker compose down
echo "  ✅ Docker Compose остановлен"

# 4. Остановить Ollama
echo "[4/4] Остановка Ollama..."
brew services stop ollama 2>/dev/null || pkill -f "ollama serve" 2>/dev/null
echo "  ✅ Ollama остановлен"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🛑 Все сервисы остановлены"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
