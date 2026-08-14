"""
SLA Checkpoint Checker — runs every minute via Celery Beat.

Implements §14 and §17 of BUSINESS_RULES.md:
1. SELECT from sla_checkpoints WHERE next_check_at <= now() AND is_processed = false
2. Lock rows with FOR UPDATE SKIP LOCKED
3. Determine recipient based on threshold and escalation rules
4. Send notifications via Telegram
5. Log to notification_log with dedup key (task_id + threshold + sla_version)
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, update, and_, text
from sqlalchemy.orm import Session

from src.tasks.celery_app import celery_app
from src.db.models import SLACheckpoint, Task, User, NotificationLog
from src.utils.config import settings

logger = logging.getLogger(__name__)

# Sync database URL (Celery tasks are synchronous)
SYNC_DB_URL = settings.DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://")

# Escalation chain (§17.3)
# threshold -> who gets notified
ESCALATION_RECIPIENTS = {
    "50%": "assignee",          # Мягкое напоминание исполнителю
    "80%": "assignee",          # Повторное напоминание исполнителю
    "100%": "department_head",  # Уведомление руководителю отдела
    "+24h": "zinovieva",        # Эскалация Зиновьевой А.
    "+48h": "lykov",            # Эскалация Лыкову М.А.
    "+72h": "alimov",           # Эскалация Алимову З.Т.
}

# Notification messages
NOTIFICATION_TEMPLATES = {
    "50%": "⏰ <b>Напоминание:</b> Задача «{title}» — прошло 50% SLA. Осталось {remaining}.",
    "80%": "⚠️ <b>Внимание:</b> Задача «{title}» — прошло 80% SLA! Осталось {remaining}.",
    "100%": "🔴 <b>ПРОСРОЧКА:</b> Задача «{title}» просрочена! Исполнитель: {assignee}.",
    "+24h": "🚨 <b>ЭСКАЛАЦИЯ +24ч:</b> Задача «{title}» просрочена более 24 часов. Исполнитель: {assignee}.",
    "+48h": "🚨🚨 <b>ЭСКАЛАЦИЯ +48ч:</b> Задача «{title}» просрочена более 48 часов! Исполнитель: {assignee}.",
    "+72h": "🚨🚨🚨 <b>ЭСКАЛАЦИЯ +72ч:</b> Задача «{title}» просрочена более 72 часов!! Требуется вмешательство ГД.",
}


@celery_app.task(name="src.tasks.sla_checker.check_sla_checkpoints")
def check_sla_checkpoints():
    """
    Periodic task: check for due SLA checkpoints and send notifications.
    Runs every 60 seconds via Celery Beat.
    """
    now = datetime.now(timezone.utc)
    logger.info(f"[SLA Checker] Running at {now.isoformat()}")

    engine = create_engine(SYNC_DB_URL)
    processed_count = 0

    with Session(engine) as session:
        # Find all due, unprocessed checkpoints with row locking
        stmt = (
            select(SLACheckpoint)
            .where(
                and_(
                    SLACheckpoint.next_check_at <= now,
                    SLACheckpoint.is_processed == False,
                )
            )
            .with_for_update(skip_locked=True)
        )
        checkpoints = session.execute(stmt).scalars().all()

        for checkpoint in checkpoints:
            try:
                # Get the task
                task = session.get(Task, checkpoint.task_id)
                if not task or task.status in ("done", "cancelled"):
                    # Task already closed, mark checkpoint as processed
                    checkpoint.is_processed = True
                    continue

                if task.status == "paused":
                    # Task is paused, skip (checkpoints will be shifted on resume)
                    continue

                # Check for dedup (§14.4)
                existing = session.execute(
                    select(NotificationLog).where(
                        and_(
                            NotificationLog.task_id == checkpoint.task_id,
                            NotificationLog.threshold == checkpoint.threshold,
                            NotificationLog.sla_version == checkpoint.sla_version,
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    # Already sent, mark as processed
                    checkpoint.is_processed = True
                    continue

                # Determine recipient
                recipient_id = _resolve_recipient(
                    session, task, checkpoint.threshold
                )

                if recipient_id:
                    # Send notification (async via separate Celery task)
                    send_sla_notification.delay(
                        task_id=str(task.id),
                        task_title=task.title,
                        threshold=checkpoint.threshold,
                        sla_version=checkpoint.sla_version,
                        recipient_telegram_id=recipient_id,
                        assignee_name=_get_user_name(session, task.assignee_id),
                    )

                    # Log notification
                    log_entry = NotificationLog(
                        task_id=checkpoint.task_id,
                        threshold=checkpoint.threshold,
                        sla_version=checkpoint.sla_version,
                        recipient_id=task.assignee_id,  # TODO: resolve actual recipient UUID
                        message_text=NOTIFICATION_TEMPLATES.get(checkpoint.threshold, ""),
                        status="sent",
                    )
                    session.add(log_entry)

                # Mark checkpoint as processed
                checkpoint.is_processed = True
                processed_count += 1

            except Exception as e:
                logger.error(f"Error processing checkpoint {checkpoint.id}: {e}")
                continue

        session.commit()

    logger.info(f"[SLA Checker] Processed {processed_count} checkpoints.")
    return {"checked_at": now.isoformat(), "processed": processed_count}


@celery_app.task(name="src.tasks.sla_checker.send_sla_notification")
def send_sla_notification(
    task_id: str,
    task_title: str,
    threshold: str,
    sla_version: int,
    recipient_telegram_id: str,
    assignee_name: str = "",
):
    """Send SLA notification via Telegram (sync wrapper)."""
    import asyncio
    from aiogram import Bot

    template = NOTIFICATION_TEMPLATES.get(threshold, "Уведомление по задаче: {title}")
    message_text = template.format(
        title=task_title,
        remaining="см. дедлайн",
        assignee=assignee_name,
    )

    async def _send():
        bot = Bot(token=settings.TELEGRAM_TOKEN)
        try:
            await bot.send_message(
                chat_id=recipient_telegram_id,
                text=message_text,
                parse_mode="HTML",
            )
            logger.info(f"Notification sent: {threshold} -> {recipient_telegram_id}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
        finally:
            await bot.session.close()

    asyncio.run(_send())


def _resolve_recipient(session: Session, task: Task, threshold: str) -> str | None:
    """
    Resolve who should receive the notification.
    §17.3: If recipient == assignee (for 100%+), use fallback chain.
    """
    role = ESCALATION_RECIPIENTS.get(threshold, "assignee")

    if role == "assignee":
        # 50% and 80% always go to assignee
        user = session.get(User, task.assignee_id)
        return user.telegram_id if user else None

    # For 100%+ escalations, we need to check the fallback chain
    # TODO: Implement full escalation chain lookup from users table
    # For now, return assignee (will be properly implemented when users are seeded)
    user = session.get(User, task.assignee_id)
    return user.telegram_id if user else None


def _get_user_name(session: Session, user_id) -> str:
    """Get user's full name."""
    user = session.get(User, user_id)
    return user.full_name if user else "Неизвестный"
