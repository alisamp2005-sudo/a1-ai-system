"""
Morning Digest Task.
Sends a daily summary to top management at 08:00 Moscow time.
"""

import logging
import asyncio
import httpx
from src.tasks.celery_app import celery_app
from src.utils.config import settings

logger = logging.getLogger(__name__)

# Telegram IDs of top management who receive the digest
# TODO: Pull from database
DIGEST_RECIPIENTS = [
    settings.ADMIN_TELEGRAM_ID,  # Admin (test)
    # Add Alimov, Zinovieva, Lykov TG IDs when available
]

DIGEST_TEMPLATE = """📊 <b>УТРЕННИЙ ДАЙДЖЕСТ — А1</b>
<i>{date}</i>

━━━━━━━━━━━━━━━━━━━━

🔴 <b>Критичное:</b>
{critical}

📋 <b>Задачи:</b>
• Всего активных: {active_tasks}
• Просрочено: {overdue_tasks}
• Создано вчера: {new_tasks}
• Закрыто вчера: {closed_tasks}

🏗 <b>Объекты:</b>
• Активных: {active_projects}
• С проблемами: {problem_projects}

👷 <b>Персонал:</b>
• В системе: {total_users}
• Активных вчера: {active_users}

━━━━━━━━━━━━━━━━━━━━

<i>Подробнее: https://ai.bruceli.ru/dashboard</i>
"""


@celery_app.task(name="src.tasks.digest.send_morning_digest")
def send_morning_digest():
    """Send morning digest to top management."""
    logger.info("Generating morning digest...")
    asyncio.run(_send_digest_async())


async def _send_digest_async():
    """Async implementation of digest sending."""
    from datetime import datetime
    import pytz

    tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(tz)
    date_str = now.strftime("%d.%m.%Y (%A)")

    # TODO: Pull real data from database
    # For now, use placeholder data
    digest_text = DIGEST_TEMPLATE.format(
        date=date_str,
        critical="Нет критичных событий ✅",
        active_tasks=0,
        overdue_tasks=0,
        new_tasks=0,
        closed_tasks=0,
        active_projects=5,
        problem_projects=0,
        total_users=5,
        active_users=1,
    )

    # Send to all recipients
    bot_token = settings.TELEGRAM_TOKEN
    if not bot_token:
        logger.error("TELEGRAM_TOKEN not set, cannot send digest")
        return

    async with httpx.AsyncClient() as client:
        for chat_id in DIGEST_RECIPIENTS:
            if not chat_id:
                continue
            try:
                url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                resp = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": digest_text,
                    "parse_mode": "HTML",
                })
                if resp.status_code == 200:
                    logger.info(f"Digest sent to {chat_id}")
                else:
                    logger.error(f"Failed to send digest to {chat_id}: {resp.text}")
            except Exception as e:
                logger.error(f"Error sending digest to {chat_id}: {e}")

    logger.info("Morning digest completed!")
