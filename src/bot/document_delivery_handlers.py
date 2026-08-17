"""Secure delivery of original knowledge-base documents through Telegram.

Document URLs are deliberately not made public. The callback is tied to the
actual Telegram account, then its role is checked against PostgreSQL before
an original PDF/Excel/Word file is sent into the chat.
"""

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery, FSInputFile
from sqlalchemy import select

from src.db.models import User
from src.db.session import async_session_factory
from src.services.document_storage import AUTHORIZED_DOCUMENT_ROLES, find_document

logger = logging.getLogger(__name__)
document_delivery_router = Router()


async def can_access_documents(telegram_id: str) -> bool:
    """Check whether an active employee may receive original documents."""
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(
                    User.telegram_id == str(telegram_id),
                    User.is_active.is_(True),
                )
            )
            user = result.scalar_one_or_none()
            return bool(user and user.role in AUTHORIZED_DOCUMENT_ROLES)
    except Exception as exc:
        logger.warning("Cannot check document access for Telegram user %s: %s", telegram_id, exc)
        return False


async def send_document_to_chat(bot, chat_id: int, telegram_id: str, document_id: str) -> tuple[bool, str]:
    """Role-check and send a stored original. Safe for callbacks and deep links."""
    if not await can_access_documents(telegram_id):
        return False, "Доступ к оригиналам документов отсутствует."

    document = find_document(document_id)
    if not document:
        return False, "Оригинал файла пока недоступен. Обратитесь к администратору."

    storage_path = Path(document["storage_path"])
    if not storage_path.is_file():
        return False, "Файл не найден на сервере."

    try:
        caption = (
            f"📄 <b>{document.get('title') or document.get('filename')}</b>\n"
            f"Категория: {document.get('category', 'прочее')}"
        )
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(storage_path, filename=document.get("filename") or storage_path.name),
            caption=caption,
        )
        return True, ""
    except Exception as exc:
        logger.exception("Document delivery failed for %s: %s", document_id, exc)
        return False, "Не удалось отправить файл. Попробуйте позже."


@document_delivery_router.callback_query(F.data.startswith("docget:"))
async def send_original_document(callback: CallbackQuery) -> None:
    """Send an original document after callback-level role verification."""
    document_id = callback.data.split(":", 1)[1]
    success, message = await send_document_to_chat(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        telegram_id=str(callback.from_user.id),
        document_id=document_id,
    )
    if success:
        await callback.answer("Документ отправлен")
    else:
        await callback.answer(message, show_alert=True)
