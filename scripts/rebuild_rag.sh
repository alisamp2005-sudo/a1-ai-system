#!/usr/bin/env bash
# Recreate only the ChromaDB vector index and rebuild the RAG corpus.
# PostgreSQL, Redis, document registry and other Docker volumes are preserved.
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

printf '\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n'
printf '  А1 RAG — пересоздание векторной базы знаний\n'
printf '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n'
printf 'Будет удален только индекс ChromaDB. PostgreSQL, Redis и реестр документов сохраняются.\n\n'

PROJECT_NAME="$(docker compose config --format json 2>/dev/null | sed -n 's/.*"name":"\([^"]*\)".*/\1/p' | head -1)"
if [[ -z "$PROJECT_NAME" ]]; then
  PROJECT_NAME="$(basename "$PROJECT_DIR")"
fi

printf '[1/5] Остановка сервисов, использующих ChromaDB...\n'
docker compose stop backend telegram_bot celery_worker celery_beat chromadb

printf '[2/5] Удаление прежнего ChromaDB-индекса...\n'
VOLUME_IDS="$(docker volume ls -q \
  --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
  --filter "label=com.docker.compose.volume=chromadata")"
if [[ -n "$VOLUME_IDS" ]]; then
  # shellcheck disable=SC2086
  docker volume rm $VOLUME_IDS
  printf '  Удален старый индекс ChromaDB.\n'
else
  printf '  Старый отдельный volume ChromaDB не найден; продолжаю.\n'
fi

printf '[3/5] Запуск совместимой версии ChromaDB и сервисов...\n'
docker compose pull chromadb
docker compose up -d --build chromadb backend telegram_bot celery_worker celery_beat

printf '[4/5] Ожидание готовности ChromaDB...\n'
for attempt in {1..30}; do
  if curl -fsS http://localhost:8000/api/v1/heartbeat >/dev/null 2>&1 \
    || curl -fsS http://localhost:8000/api/v2/heartbeat >/dev/null 2>&1; then
    printf '  ChromaDB готов.\n'
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    printf '  Ошибка: ChromaDB не стал доступен за 60 секунд.\n' >&2
    docker compose logs chromadb --tail 80 >&2
    exit 1
  fi
  sleep 2
done

printf '[5/5] Повторная загрузка нормативной базы знаний...\n'
python3 -m pip install --user "chromadb==0.5.5" >/dev/null
python3 scripts/load_rag_documents.py

printf '\n✅ RAG восстановлен. Проверка: отправьте боту вопрос по ТБ или откройте админку → «База знаний».\n'
