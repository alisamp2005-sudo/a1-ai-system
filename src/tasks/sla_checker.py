"""SLA Checkpoint Checker — runs every minute via Celery Beat.

Implements §14 of BUSINESS_RULES.md:
1. SELECT from sla_checkpoints WHERE next_check_at <= now() AND is_processed = false
2. Lock rows with FOR UPDATE SKIP LOCKED
3. Send notifications via Telegram
4. Log to notification_log with dedup key (task_id + threshold + sla_version)
"""

import logging
from datetime import datetime, timezone

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.sla_checker.check_sla_checkpoints")
def check_sla_checkpoints():
    """
    Periodic task: check for due SLA checkpoints and send notifications.
    This is a synchronous Celery task that uses sync DB access.
    """
    logger.info(f"[SLA Checker] Running at {datetime.now(timezone.utc).isoformat()}")

    # TODO: Phase 1 implementation
    # 1. Connect to PostgreSQL (sync)
    # 2. SELECT * FROM sla_checkpoints
    #    WHERE next_check_at <= NOW() AND is_processed = FALSE
    #    FOR UPDATE SKIP LOCKED
    # 3. For each checkpoint:
    #    a. Determine recipient based on threshold and escalation rules
    #    b. Check notification_log for dedup (task_id + threshold + sla_version)
    #    c. Send Telegram notification
    #    d. Mark checkpoint as is_processed = True
    #    e. Insert into notification_log

    logger.info("[SLA Checker] Complete.")
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "processed": 0}
