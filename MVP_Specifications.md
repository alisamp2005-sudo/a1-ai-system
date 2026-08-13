# Спецификация MVP (Фаза 0 + Фаза 1)

Этот документ описывает точные технические требования к первой версии системы (MVP), чтобы разработка могла начаться без дополнительных согласований.

## 1. Границы MVP

В рамках MVP реализуются только базовые функции маршрутизации, создания задач и контроля SLA. Профильные агенты (Юрист, Финансист и т.д.) будут добавлены в Фазе 2.

**Что входит в MVP:**
- Развертывание локальной инфраструктуры (Mac Mini, Ollama, Docker).
- Telegram-бот с базовой авторизацией (по номеру телефона).
- Интеграция Whisper для транскрибации голосовых сообщений.
- Диспетчер (Router) на базе LangGraph и Llama 3.1 8B для классификации запросов.
- Подсистема задач (Celery + Redis) для отслеживания SLA.
- Алгоритм эскалации (до уровня ГД).

## 2. API-Контракты (Внутренние)

### 2.1. Создание задачи (SLA)
Вызывается, когда Диспетчер определяет, что запрос требует контроля времени.

```json
POST /api/v1/tasks
{
  "title": "Подготовить отчет по объекту Михалковская",
  "assignee_id": "telegram_id_12345",
  "project_id": "uuid-object-1",
  "priority": "P2",
  "deadline": "2026-04-15T18:00:00Z"
}
```

### 2.2. Обработка эскалации (Celery Worker)
Функция, которая срабатывает по таймеру SLA.

```python
@celery.task
def check_sla_and_escalate(task_id: str, threshold: str):
    # threshold = '50%', '80%', '100%', '+24h', '+48h', '+72h'
    task = db.get_task(task_id)
    if task.status == 'done':
        return
    
    escalation_user_id = get_escalation_target(task, threshold)
    send_telegram_message(escalation_user_id, generate_alert_text(task, threshold))
```

## 3. Миграции БД (MVP)

Для MVP необходимы три базовые таблицы.

**Таблица `users`:**
- `id` (UUID, Primary Key)
- `telegram_id` (BIGINT, Unique)
- `full_name` (VARCHAR)
- `role` (VARCHAR) — admin, top_manager, manager, worker
- `phone_number` (VARCHAR)

**Таблица `projects`:**
- `id` (UUID, Primary Key)
- `name` (VARCHAR)
- `manager_id` (UUID, Foreign Key -> users.id)

**Таблица `tasks`:**
- `id` (UUID, Primary Key)
- `title` (VARCHAR)
- `assignee_id` (UUID, Foreign Key -> users.id)
- `project_id` (UUID, Foreign Key -> projects.id)
- `status` (VARCHAR) — new, in_progress, done
- `priority` (VARCHAR) — P0, P1, P2, P3
- `created_at` (TIMESTAMP)
- `deadline` (TIMESTAMP)

## 4. Критерии приемки (Acceptance Criteria)

MVP считается успешно завершенным, если выполняются следующие условия:

1. **Авторизация:** Пользователь может запустить бота, отправить контакт, и бот узнает его по базе данных. Неизвестные номера отклоняются.
2. **Голос в текст:** Пользователь может отправить голосовое сообщение, и бот возвращает корректную текстовую расшифровку (Whisper).
3. **Маршрутизация:** Диспетчер корректно классифицирует 9 из 10 тестовых запросов, определяя приоритет (P0-P3) и целевой отдел.
4. **Контроль SLA:** При создании тестовой задачи с SLA = 1 час, система автоматически присылает напоминания исполнителю через 30 минут (50%) и 48 минут (80%), а через 1 час — уведомление руководителю.
5. **Безопасность:** Все запросы к LLM обрабатываются локально на Mac Mini. Сетевой трафик не уходит на серверы OpenAI или Anthropic.
