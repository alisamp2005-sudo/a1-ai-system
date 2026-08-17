# PROJECT_STATUS.md — А1 AI System

**Дата обновления:** 2026-08-17  
**Репозиторий:** https://github.com/alisamp2005-sudo/a1-ai-system  
**Бот:** @a1stroibot  
**Домен:** https://ai.bruceli.ru

---

## 1. Текущие цели

Построить полностью локальную AI-систему управления строительной компанией «ООО А1» (16 объектов, Москва и регионы). Система работает как Telegram-бот с 7 специализированными AI-агентами, SLA-контролем, эскалацией, RAG-базой знаний, web-панелью администратора и Mini App для прорабов.

Ключевое ограничение: все LLM-вычисления выполняются локально на Mac Mini M4 Pro 64 ГБ через Ollama. Telegram допускается только как транспорт.

---

## 2. Завершённые задачи

### Фаза 0 — Инфраструктура
- Docker Compose: 8 сервисов (postgres, redis, chromadb, backend, telegram_bot, telegram_bot_api, celery_worker, celery_beat)
- Ollama 0.32.9: Qwen 2.5 32B, Llama 3.1 8B, nomic-embed-text
- Cloudflare Tunnel: ai.bruceli.ru → localhost:8080 (protocol http2, QUIC заблокирован провайдером)
- macOS автозапуск: LaunchAgents для Docker, Vision, Whisper, Tunnel

### Фаза 1 — Ядро
- Telegram-бот (aiogram 3.13) с persistent menu (3 ряда кнопок)
- Router Agent — классификация сообщений в JSON (task_type, priority, needs_complex_model)
- QA Controller — проверка ответов на галлюцинации (severity: high/medium/low)
- SLA Controller — Celery Beat (каждую минуту), 6-уровневая эскалация
- Whisper-сервис на хосте (порт 11436, faster-whisper, модель large-v3)
- Память разговоров — Redis, последние 20 сообщений + сводка старых (summarization memory)
- Seed DB: 5 пользователей, 7 отделов, 16 реальных объектов, 8 правил маршрутизации

### Фаза 2 — AI-агенты
- Secretary (project_management) — с методом process_question
- Lawyer — заглушка для будущей интеграции Yandex AI
- Finance, Procurement, HR, Analyst, Reporter/Digest
- Safety/Vision — двухшаговый: mlx-vlm (английский анализ) → Ollama Llama 8B (перевод на русский)

### Фаза 3 — Интерфейсы
- Web Dashboard: /dashboard — статистика, задачи
- Admin Panel: /admin — авторизация (login/password), CRUD сотрудников, объектов, отделов
- Admin: вкладка «📚 База знаний» — список документов, загрузка файлов с комментариями/отделом/объектом
- Admin: вкладка «📋 Отчёты» — таблица отчётов со стройки с сортировкой
- Admin: статусы объектов (активный/завершённый), бот не видит завершённые
- Admin: поле telegram_username для сотрудников
- Telegram Mini App: /miniapp/report — форма ежедневного отчёта прораба
- Карточки объектов: /miniapp/object/{name} — с документами (видны только top_manager/admin)
- Inline-кнопки под ответами бота (объекты, сотрудники) → карточки в Mini App
- Кнопки одобрения ГД (5 кнопок: Утвердить/Отклонить/Уточнить/Делегировать/Отложить)

### Фаза 4 — RAG и данные
- ChromaDB: 70 фрагментов из 11 нормативных документов (СНиП, ГОСТ, Приказы, ГК РФ)
- Агенты ищут в RAG перед ответом
- Агенты получают реальные данные из PostgreSQL (db_context)
- Загрузка документов через бота (PDF, DOCX, XLSX, TXT, CSV, PPTX + OCR для фото)
- Загрузка документов через админку (форма с файлом, категорией, отделом, объектом, комментарием)
- Синхронизация Яндекс.Диска (ежедневно 06:00 МСК, Celery Beat)
- Защита от дубликатов (по хэшу содержимого)
- Антигаллюцинационные промпты: «Если нет данных — скажи прямо»
- 16 реальных объектов загружены из Яндекс.Диска
- Подготовлено восстановление RAG: ChromaDB server/client закреплены на совместимой версии 0.5.5; создан `scripts/rebuild_rag.sh` для безопасного пересоздания только векторного индекса
- Единый API RAG для Telegram, админки и синхронизации Яндекс.Диска: `add_text_document()` разбивает документ на фрагменты и возвращает фактически сохранённое количество

### Утренний дайджест
- Celery Beat, 08:00 МСК, отправляется admin ID
- Команда /digest для ручного вызова

---

## 3. Ключевые технические решения

| Решение | Обоснование |
|---------|-------------|
| Ollama + Qwen 32B / Llama 8B | Qwen для сложных задач (юрист, аналитик), Llama 8B для быстрой классификации и простых агентов |
| mlx-vlm для Vision | Ollama 0.32.9 не поддерживает mllama; mlx-vlm работает нативно на Apple Silicon |
| Двухшаговый Vision | Llama 3.2 Vision 11B (8-bit) анализирует на английском → Llama 8B переводит на русский |
| Whisper на хосте | Docker не имеет доступа к Metal GPU; модель кэшируется навсегда |
| Redis для памяти | 20 последних сообщений + summarization старых; очистка через FLUSHALL |
| ChromaDB для RAG | Векторный поиск, nomic-embed-text для embeddings |
| Celery Beat | SLA-проверка каждую минуту, дайджест 08:00, синхронизация Я.Диска 06:00 |
| Cloudflare Tunnel http2 | QUIC заблокирован российским провайдером |
| Telegram Bot API Local Server | Снимает лимит 20 МБ на файлы (до 2 ГБ) |
| db_context + RAG | Агенты получают данные из PostgreSQL И из базы знаний перед ответом |
| QA skip при наличии db_info | Когда данные из БД — QA не блокирует (предотвращает ложные отклонения) |

---

## 4. Основные файлы проекта

### Конфигурация
- `docker-compose.yml` — 8 сервисов, volumes для src/config/data
- `requirements.txt` — зависимости Python (pydantic<2.9, tenacity<9, langgraph 0.2.28)
- `.env` (НЕ в git) — TELEGRAM_TOKEN, DB_PASS, ADMIN_TELEGRAM_ID, OLLAMA_URL

### Бот
- `src/bot/main.py` — инициализация aiogram, регистрация роутеров, поддержка Local API
- `src/bot/handlers.py` — основной обработчик текста, фото, голосовых; inline-кнопки
- `src/bot/document_handlers.py` — загрузка файлов в RAG через бота
- `src/bot/task_handlers.py` — /newtask, /mytasks, /digest, /users
- `src/bot/approval_handlers.py` — кнопки одобрения ГД

### Сервисы
- `src/services/router_agent.py` — классификация + маршрутизация + вызов агентов + RAG + db_context
- `src/services/memory_service.py` — Redis, 20 сообщений + summarization
- `src/services/rag_service.py` — поиск в ChromaDB, add_document
- `src/services/db_context.py` — получение объектов/сотрудников из PostgreSQL
- `src/services/qa_controller.py` — проверка ответов на галлюцинации
- `src/services/ollama_client.py` — HTTP-клиент к Ollama
- `src/services/whisper_service.py` — HTTP-клиент к Whisper-сервису на хосте
- `src/services/document_processor.py` — извлечение текста из 18 форматов
- `src/services/inline_links.py` — автоматические inline-кнопки
- `src/services/yadisk_sync.py` — синхронизация Яндекс.Диска

### API
- `src/api/main.py` — FastAPI app, SessionMiddleware
- `src/api/admin.py` — админка с авторизацией, CRUD, загрузка документов
- `src/api/dashboard.py` — web-дашборд
- `src/api/miniapp.py` — Mini App форма отчёта
- `src/api/cards.py` — карточки объектов/сотрудников

### Задачи (Celery)
- `src/tasks/celery_app.py` — конфигурация, beat_schedule
- `src/tasks/sla_checker.py` — проверка SLA каждую минуту
- `src/tasks/digest.py` — утренний дайджест
- `src/tasks/yadisk_sync_task.py` — синхронизация Яндекс.Диска

### Скрипты (запускаются на хосте)
- `scripts/start_all.sh` — запуск всего одной командой
- `scripts/stop_all.sh` — остановка всего
- `scripts/install_autostart.sh` — установка LaunchAgents
- `scripts/vision_service.py` — Vision-сервис (порт 11435)
- `scripts/whisper_service.py` — Whisper-сервис (порт 11436)
- `scripts/load_rag_documents.py` — загрузка нормативов в RAG
- `scripts/update_projects.py` — обновление объектов в БД
- `scripts/seed_db.py` — начальное заполнение БД

---

## 5. Результаты тестирования

| Функция | Статус | Примечание |
|---------|--------|------------|
| Классификация сообщений (Router) | ✅ Работает | Иногда возвращает list вместо dict — обработано fallback |
| Ответы по объектам из БД | ✅ Работает | 16 объектов, реальные адреса |
| Голосовые сообщения (Whisper) | ✅ Работает | Сервис на хосте, порт 11436 |
| Анализ фото (Vision) | ⚠️ Частично | Модель галлюцинирует (видит нарушения где их нет). Нужно fine-tuning |
| Память разговоров | ✅ Работает | Бот помнит контекст (проверено: «по какому она адресу?» после вопроса об объекте) |
| RAG (база знаний) | 🟡 Ожидает развёртывания фикса | Код исправлен: сервер/клиент ChromaDB закреплены на 0.5.5, добавлен безопасный rebuild-скрипт. Нужна проверка на Mac после запуска скрипта. |
| Inline-кнопки | ✅ Работает | Появляются при упоминании 1-6 объектов |
| Антигаллюцинация | ✅ Работает | Бот говорит «данных нет» вместо выдумывания |
| Админка — авторизация | ✅ Работает | login/password |
| Админка — sidebar кнопки | ⚠️ Нестабильно | JS-функции иногда не определяются глобально |
| Загрузка документов через бота | ✅ Работает | Лимит 20 МБ (Local API не настроен — нет TELEGRAM_API_ID/HASH) |
| Синхронизация Яндекс.Диска | 🟡 Ожидает проверки | Исправлены API-пути папок, обработка результата `extract_text()` и вызов RAG. Нужен ручной прогон после восстановления RAG. |
| Утренний дайджест | ✅ Настроен | Шаблонные данные (мало реальных задач) |
| SLA-эскалация | ✅ Настроена | Нет реальных задач для проверки |
| Cloudflare Tunnel | ✅ Работает | http2, 4 соединения |

---

## 6. Известные проблемы

### Критичные (блокируют функционал)

1. **RAG требует развёртывания исправления на Mac** — причина `tenant default_tenant` установлена: использовался образ `chromadb/chroma:latest` при Python-клиенте 0.5.x. В коде закреплена совместимая пара 0.5.5 и добавлен `scripts/rebuild_rag.sh`, однако старый индекс нужно пересоздать и проверить на рабочем Mac.

2. **Telegram Bot API Local Server не настроен** — в .env отсутствуют TELEGRAM_API_ID и TELEGRAM_API_HASH. Docker-compose ругается warning. Лимит файлов остаётся 20 МБ. Для настройки: получить api_id/hash на my.telegram.org.

3. **Синхронизация Яндекс.Диска ожидает первого успешного прогона** — в коде устранены неверные пути папок, несовместимый вызов RAG и обработка результата Excel. После восстановления RAG следует запустить синхронизацию вручную и сверить реестр документов.

### Средние

4. **Admin panel JS** — функции иногда не определяются глобально (showTab, editUser). Причина: если loadUsers() падает с ошибкой при DOMContentLoaded, весь скрипт прерывается до определения остальных функций. Решение: обернуть каждую async-функцию в try/catch.

5. **Vision-агент галлюцинирует** — Llama 3.2 Vision 11B (8-bit) не различает наличие/отсутствие касок. Решение: fine-tuning (см. docs/VISION_FINETUNING_GUIDE.md) или YOLO для детекции СИЗ.

6. **Дубликат «Хранилища»** — объект дублируется в списке (2 записи в БД). Нужно удалить одну.

### Низкие

7. **Dashboard показывает частично статичные данные** — не все виджеты подключены к реальной БД.
8. **Таблица daily_reports не создана** — нужно выполнить CREATE TABLE (SQL приведён ниже).
9. **TELEGRAM_API_ID/HASH warnings** — безвредные, но засоряют логи.

---

## 7. Подходы, которые не сработали

| Подход | Проблема | Альтернатива |
|--------|----------|--------------|
| Ollama 0.32.9 + llama3.2-vision:11b | `unknown model architecture: 'mllama'` — Ollama не поддерживает | mlx-vlm на хосте |
| llama.cpp (brew, v10360) + ollama blob | Тот же `unknown model architecture: 'mllama'` — формат Ollama несовместим | mlx-vlm |
| mlx-vlm 4-bit (Llama-3.2-11B-Vision-Instruct-4bit) | Сильные галлюцинации, ломаный русский | 8-bit версия + перевод через Llama 8B |
| Vision-промпт на русском | Модель путает русский с транслитерацией | Английский промпт + перевод |
| Whisper внутри Docker | Модель 3 ГБ скачивается при каждом перезапуске, нет Metal GPU | Whisper-сервис на хосте |
| Длинный список объектов в Router-промпте | Модель копирует список вместо JSON-классификации | Убрали список, оставили только ключевые слова |
| QA Controller для project_management | Ложные отклонения (блокировал корректные ответы из БД) | Skip QA когда есть db_info |
| inline onclick="showTab(...)" | Функции не в global scope | window.showTab = showTab |
| Template literals в JS (admin.py) | Экранирование кавычек в onclick ломает парсинг | data-* атрибуты + addEventListener |
| ngrok для SSH-доступа | Заблокирован из России (ERR_NGROK_9040) | Cloudflare Tunnel |

---

## 8. Следующие шаги разработки

### Приоритет 1 — Исправить блокеры

1. **Развернуть и проверить RAG-фикс на Mac** — после `git pull` выполнить `./scripts/rebuild_rag.sh`; подтвердить, что бот находит нормативный контекст и в админке видны документы.
2. **Проверить синхронизацию Яндекс.Диска** — после RAG rebuild запустить вручную, убедиться, что вложенные файлы загрузились, связались с объектами и не дублируются.
3. **Починить JS в админке** — обернуть async-функции в try/catch, добавить console.error для диагностики.

### Приоритет 2 — Данные и интеграции

4. **Получить TELEGRAM_API_ID/HASH** — настроить Local API для файлов >20 МБ.
5. **Получить Telegram ID руководства** — Алимов, Зиновьева, Лыков → включить реальную эскалацию.
6. **Заполнить реальные данные** — адреса всех объектов, сотрудники с TG ID через админку.
7. **Интеграция Yandex AI Юрист** — гибридный агент (ответы сохраняются в RAG, со временем заменяется локальным).
8. **Создать таблицу daily_reports** — для хранения отчётов прорабов.

### Приоритет 3 — Качество и пилот

9. **Fine-tuning Vision** — собрать 200-300 фото с объектов, обучить через mlx_vlm.lora.
10. **Подключить dashboard к реальной БД** — статистика задач, SLA-метрики.
11. **Загрузить реальные документы** — договоры, регламенты компании, сметы.
12. **Пилот на 3 объектах** — когда будут данные и ID сотрудников.

### Приоритет 4 — Улучшения

13. **Команда /link** — связать Telegram ID с сотрудником (самостоятельная регистрация).
14. **Обновить Ollama** — когда выйдет поддержка mllama, перевести Vision на Ollama.
15. **YOLO для касок/жилетов** — точнее чем LLM для детекции конкретных объектов.
16. **Уведомления о новых документах в дайджесте** — что синхронизировалось с Я.Диска.

---

## 9. Архитектура сервисов на Mac Mini

```
┌─────────────────────────────────────────────────────────────┐
│  Mac Mini M4 Pro 64 ГБ (хост)                               │
├─────────────────────────────────────────────────────────────┤
│  Ollama (порт 11434)      — Qwen 32B, Llama 8B, nomic      │
│  Vision-сервис (порт 11435) — mlx-vlm, Llama 3.2 Vision 8bit│
│  Whisper-сервис (порт 11436) — faster-whisper, large-v3     │
│  Cloudflare Tunnel         — ai.bruceli.ru → localhost:8080  │
├─────────────────────────────────────────────────────────────┤
│  Docker Compose:                                             │
│    postgres:5432  redis:6379  chromadb:8000                  │
│    backend:8080  telegram_bot  telegram_bot_api:8081         │
│    celery_worker  celery_beat                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 10. Команды для быстрого старта

```bash
# Запуск всего
cd ~/a1-ai-system && ./scripts/start_all.sh

# Остановка всего
cd ~/a1-ai-system && ./scripts/stop_all.sh

# Обновление кода
cd ~/a1-ai-system && git checkout -- . && git pull && docker compose up -d --build

# Перезапуск бота
docker compose restart telegram_bot

# Перезапуск backend (админка)
docker compose restart backend

# Логи бота
docker compose logs telegram_bot --tail 20

# Очистка памяти бота
docker compose exec redis redis-cli FLUSHALL

# Безопасное восстановление RAG после обновления ChromaDB
./scripts/rebuild_rag.sh

# Низкоуровневый загрузчик нормативов (сам пересоздаёт коллекцию; обычно используйте rebuild_rag.sh)
python3 scripts/load_rag_documents.py

# Синхронизация Яндекс.Диска (вручную)
docker compose exec celery_worker python -c "import asyncio; from src.services.yadisk_sync import sync_yadisk; print(asyncio.run(sync_yadisk()))"

# Обновление объектов в БД
python3 scripts/update_projects.py

# Запуск Vision-сервиса
python3 scripts/vision_service.py

# Запуск Whisper-сервиса
python3 scripts/whisper_service.py
```

---

## 11. Переменные окружения (.env, НЕ в git)

Файл `.env` должен содержать следующие ключи (значения не приводятся):

```
TELEGRAM_TOKEN
DB_USER
DB_PASS
DB_NAME
DATABASE_URL
REDIS_URL
OLLAMA_URL
ADMIN_TELEGRAM_ID
TIMEZONE
VISION_SERVICE_URL
WHISPER_SERVICE_URL
TELEGRAM_API_ID        # опционально, для Local API
TELEGRAM_API_HASH      # опционально, для Local API
TELEGRAM_LOCAL_API_URL  # опционально, для Local API
```

---

## 12. Celery Beat расписание

| Задача | Расписание | Описание |
|--------|-----------|----------|
| check_sla_checkpoints | Каждые 60 секунд | Проверка SLA, отправка эскалаций |
| send_morning_digest | 08:00 МСК | Утренняя сводка admin ID |
| sync_yadisk | 06:00 МСК | Синхронизация документов с Яндекс.Диска |

---

## 13. SQL для создания таблицы отчётов (выполнить на маке)

```sql
CREATE TABLE IF NOT EXISTS daily_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    project_name VARCHAR(255),
    author_id UUID REFERENCES users(id),
    author_name VARCHAR(255),
    telegram_user_id VARCHAR,
    report_date DATE DEFAULT CURRENT_DATE,
    workers_count INTEGER,
    work_done TEXT,
    problems TEXT,
    materials_needed TEXT,
    notes TEXT,
    weather VARCHAR(100),
    status VARCHAR(20) DEFAULT 'new',
    reviewed_by UUID REFERENCES users(id),
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_reports_date ON daily_reports(report_date);
CREATE INDEX IF NOT EXISTS ix_reports_project ON daily_reports(project_id);
```

---

## 14. Публичная ссылка Яндекс.Диска (источник документов)

```
https://disk.yandex.ru/d/-4W75tS2bYOqWw
```

16 папок по объектам + Реестр контрактов 2026.xlsx в корне.
