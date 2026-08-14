#!/bin/bash
# ============================================================
# А1 AI System — Установка автозапуска (LaunchAgent)
# Запуск: cd ~/a1-ai-system && ./scripts/install_autostart.sh
# ============================================================

set -e

PLIST_DIR="$HOME/Library/LaunchAgents"
SCRIPT_DIR="$HOME/a1-ai-system/scripts"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🏗 А1 AI System — Установка автозапуска"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Создаём директорию если нет
mkdir -p "$PLIST_DIR"

# 1. LaunchAgent для Docker Compose
cat > "$PLIST_DIR/com.a1.docker-compose.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.a1.docker-compose</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/docker</string>
        <string>compose</string>
        <string>-f</string>
        <string>$HOME/a1-ai-system/docker-compose.yml</string>
        <string>up</string>
        <string>-d</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$HOME/a1-ai-system</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>StandardOutPath</key>
    <string>/tmp/a1-docker-compose.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/a1-docker-compose.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Docker Compose LaunchAgent создан"

# 2. LaunchAgent для Vision-сервиса
cat > "$PLIST_DIR/com.a1.vision-service.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.a1.vision-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$HOME/a1-ai-system/scripts/vision_service.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$HOME/a1-ai-system</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/a1-vision-service.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/a1-vision-service.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Vision Service LaunchAgent создан"

# 3. LaunchAgent для Cloudflare Tunnel
cat > "$PLIST_DIR/com.a1.cloudflare-tunnel.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.a1.cloudflare-tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>--protocol</string>
        <string>http2</string>
        <string>run</string>
        <string>a1-system</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$HOME</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/a1-cloudflare-tunnel.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/a1-cloudflare-tunnel.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Cloudflare Tunnel LaunchAgent создан"

# 4. LaunchAgent для Whisper-сервиса
cat > "$PLIST_DIR/com.a1.whisper-service.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.a1.whisper-service</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$HOME/a1-ai-system/scripts/whisper_service.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$HOME/a1-ai-system</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/a1-whisper-service.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/a1-whisper-service.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

echo "✅ Whisper Service LaunchAgent создан"

# Загружаем все LaunchAgents
echo ""
echo "Загрузка LaunchAgents..."

launchctl load "$PLIST_DIR/com.a1.docker-compose.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.a1.vision-service.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.a1.whisper-service.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.a1.cloudflare-tunnel.plist" 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎉 Автозапуск установлен!"
echo ""
echo "  При перезагрузке мака автоматически запустятся:"
echo "  1. Docker Compose (все 7 контейнеров)"
echo "  2. Vision-сервис (порт 11435)"
echo "  3. Cloudflare Tunnel (ai.bruceli.ru)"
echo ""
echo "  Ollama запускается автоматически через brew services."
echo ""
echo "  Логи:"
echo "  • Docker: /tmp/a1-docker-compose.log"
echo "  • Vision: /tmp/a1-vision-service.log"
echo "  • Tunnel: /tmp/a1-cloudflare-tunnel.log"
echo ""
echo "  Для удаления автозапуска:"
echo "  launchctl unload ~/Library/LaunchAgents/com.a1.*.plist"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
