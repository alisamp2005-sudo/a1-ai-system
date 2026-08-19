"""Closed-access middleware for the A1 Telegram bot.

Only active employees from PostgreSQL can use bot handlers. Employees entered by
username are bound to their stable Telegram ID on their first verified message.
Unknown accounts receive one access notice and no business functions are run.
"""

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from src.services.employee_identity import resolve_employee

logger = logging.getLogger(__name__)
ACCESS_DENIED_TEXT = (
    "⛔ <b>Доступ к AI-системе А1 не предоставлен.</b>\n\n"
    "Ваш Telegram-аккаунт отсутствует в реестре сотрудников. "
    "Обратитесь к администратору для добавления в систему."
)


class EmployeeAccessMiddleware(BaseMiddleware):
    """Block bot operations for users outside the active employee roster."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return await handler(event, data)

        employee = await resolve_employee(
            telegram_id=str(from_user.id),
            telegram_username=from_user.username,
        )
        if employee:
            data["employee"] = employee
            return await handler(event, data)

        logger.warning("Blocked unrecognized Telegram account: %s", from_user.id)
        if isinstance(event, Message):
            await event.answer(ACCESS_DENIED_TEXT)
        elif isinstance(event, CallbackQuery):
            await event.answer("Доступ не предоставлен.", show_alert=True)
        return None
