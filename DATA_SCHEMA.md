# Схема Базы Данных (PostgreSQL 16)

В системе используется реляционная база данных PostgreSQL 16. Для RAG используется отдельная векторная база ChromaDB.

## Основные таблицы

### 1. `users` (Пользователи)
- `id` (PK, UUID)
- `telegram_id` (BIGINT, Unique)
- `full_name` (VARCHAR)
- `role_id` (FK -> roles.id)
- `department_id` (FK -> departments.id)
- `is_active` (BOOLEAN)

### 2. `roles` (Роли и права)
- `id` (PK, INT)
- `name` (VARCHAR) — например, 'admin', 'manager', 'worker'
- `permissions` (JSONB)

### 3. `projects` (Строительные объекты)
- `id` (PK, UUID)
- `name` (VARCHAR)
- `address` (VARCHAR)
- `status` (VARCHAR)
- `manager_id` (FK -> users.id) — РП объекта
- `start_date` (DATE)
- `end_date` (DATE)

### 4. `tasks` (Задачи и поручения)
- `id` (PK, UUID)
- `title` (VARCHAR)
- `description` (TEXT)
- `creator_id` (FK -> users.id)
- `assignee_id` (FK -> users.id)
- `project_id` (FK -> projects.id, Nullable)
- `priority` (VARCHAR) — P0, P1, P2, P3
- `status` (VARCHAR) — 'new', 'in_progress', 'review', 'done', 'overdue'
- `created_at` (TIMESTAMP)
- `deadline` (TIMESTAMP)
- `completed_at` (TIMESTAMP, Nullable)

### 5. `escalations` (Лог эскалаций)
- `id` (PK, UUID)
- `task_id` (FK -> tasks.id)
- `level` (INT) — 1 (50%), 2 (80%), 3 (100%), 4 (+24h), 5 (+48h), 6 (+72h)
- `notified_user_id` (FK -> users.id)
- `created_at` (TIMESTAMP)

### 6. `chat_history` (История сообщений для LangGraph)
- `id` (PK, UUID)
- `thread_id` (UUID) — идентификатор диалога
- `user_id` (FK -> users.id)
- `agent_name` (VARCHAR)
- `message` (TEXT)
- `is_from_bot` (BOOLEAN)
- `created_at` (TIMESTAMP)

### 7. `documents` (Метаданные файлов для RAG)
- `id` (PK, UUID)
- `filename` (VARCHAR)
- `file_path` (VARCHAR)
- `doc_type` (VARCHAR) — 'contract', 'snip', 'gost', 'reg'
- `uploaded_at` (TIMESTAMP)
- `chroma_collection_id` (VARCHAR)

### 8. `daily_reports` (Отчеты прорабов)
- `id` (PK, UUID)
- `project_id` (FK -> projects.id)
- `author_id` (FK -> users.id)
- `report_date` (DATE)
- `content` (JSONB) — выполненные объемы, проблемы
- `photos` (JSONB) — пути к файлам

### 9. `safety_violations` (Нарушения ТБ от Vision)
- `id` (PK, UUID)
- `project_id` (FK -> projects.id)
- `photo_path` (VARCHAR)
- `violation_type` (VARCHAR)
- `detected_at` (TIMESTAMP)
- `status` (VARCHAR) — 'new', 'fixed'
