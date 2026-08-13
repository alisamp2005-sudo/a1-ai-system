"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab
from src.utils.config import settings

celery_app = Celery(
    "a1_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
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
)

# Beat schedule: check SLA every minute
celery_app.conf.beat_schedule = {
    "check-sla-every-minute": {
        "task": "src.tasks.sla_checker.check_sla_checkpoints",
        "schedule": settings.SLA_CHECK_INTERVAL_SECONDS,
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks(["src.tasks"])
