"""
Yandex Disk Sync Task.
Runs daily at 06:00 Moscow time — syncs documents from public Yandex Disk folder.
"""

import logging
import asyncio

from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="sync_yadisk")
def sync_yadisk_task():
    """Celery task to sync Yandex Disk documents."""
    logger.info("Starting scheduled Yandex Disk sync...")
    try:
        from src.services.yadisk_sync import sync_yadisk
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(sync_yadisk())
        loop.close()
        logger.info(f"Yandex Disk sync completed: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Yandex Disk sync failed: {e}")
        return {"error": str(e)}
