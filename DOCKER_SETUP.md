# Инфраструктура и Docker Setup

Все компоненты системы разворачиваются на Mac Mini M4 Pro с использованием Docker Compose (за исключением Ollama, которая ставится нативно (bare-metal) для лучшей утилизации MLX/Apple Silicon).

## Архитектура развертывания

1. **Host OS (macOS):**
   - Ollama (нативный бинарник, использует GPU/Neural Engine)
   - Cloudflare Tunnel (нативный демон)

2. **Docker Compose (Контейнеры):**
   - `postgres`: PostgreSQL 16
   - `redis`: Redis 7 (брокер сообщений для Celery)
   - `chromadb`: Векторная БД для RAG
   - `backend`: FastAPI + LangGraph + aiogram
   - `celery_worker`: Воркеры для фоновых задач
   - `celery_beat`: Планировщик для SLA
   - `frontend`: Nginx + React (Дашборд и Админка)

## Примерный `docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: a1_system
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chromadata:/chroma/chroma

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@postgres:5432/a1_system
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_URL=http://host.docker.internal:11434
      - TELEGRAM_TOKEN=${TG_TOKEN}
    ports:
      - "8080:8080"
    depends_on:
      - postgres
      - redis
      - chromadb
    extra_hosts:
      - "host.docker.internal:host-gateway"

  celery_worker:
    build: ./backend
    command: celery -A core.tasks worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@postgres:5432/a1_system
      - REDIS_URL=redis://redis:6379/0
      - OLLAMA_URL=http://host.docker.internal:11434
    depends_on:
      - redis
      - postgres

volumes:
  pgdata:
  chromadata:
```

## Доступ извне

Для доступа к Telegram Webhooks, Дашборду и Админке из интернета (без белого IP) используется **Cloudflare Tunnel**.
Он пробрасывает локальные порты 8080 (API) и 80 (Frontend) на защищенные домены (например, `api.a1-build.ru` и `admin.a1-build.ru`).
