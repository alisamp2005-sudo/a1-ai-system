"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab
from src.utils.config import settings

celery_app = Celery(
    "a1_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "src.tasks.sla_checker",
        "src.tasks.digest",
        "src.tasks.yadisk_sync_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# Beat schedule
celery_app.conf.beat_schedule = {
    "check-sla-every-minute": {
        "task": "src.tasks.sla_checker.check_sla_checkpoints",
        "schedule": settings.SLA_CHECK_INTERVAL_SECONDS,
    },
    "morning-digest-08-00": {
        "task": "src.tasks.digest.send_morning_digest",
        "schedule": crontab(hour=8, minute=0),  # 08:00 Moscow time
    },
    "yadisk-sync-daily-06-00": {
        "task": "sync_yadisk",
        "schedule": crontab(hour=6, minute=0),  # 06:00 Moscow time
    },
}

# Task modules are explicitly listed in the Celery constructor above. This is
# required because the worker starts from src.tasks.celery_app, not a package
# that automatically imports all task-declaration modules.
