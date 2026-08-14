"""
Approval handlers — inline buttons for task approval by management.

Implements the GD approval flow:
- ✅ Согласовать
- ❌ Отклонить
- ❓ Уточнить
- 👉 Делегировать
- ⏸ Отложить
"""

import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message

logger = logging.getLogger(__name__)
approval_router = Router()


# ================================================================
# KEYBOARDS
# ================================================================

def get_approval_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Generate approval buttons for a task."""
    buttons = [
        [
            InlineKeyboardButton(
                text="✅ Согласовать",
                callback_data=f"approve_{task_id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"reject_{task_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="❓ Уточнить",
                callback_data=f"clarify_{task_id}"
            ),
            InlineKeyboardButton(
                text="👉 Делегировать",
                callback_data=f"delegate_{task_id}"
            ),
        ],
        [
            InlineKeyboardButton(
                text="⏸ Отложить",
                callback_data=f"postpone_{task_id}"
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_delegate_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Generate delegation target buttons."""
    buttons = [
        [InlineKeyboardButton(
            text="👤 Зиновьева А. (Исп. директор)",
            callback_data=f"delegateto_zinovieva_{task_id}"
        )],
        [InlineKeyboardButton(
            text="👤 Лыков М.А. (Зам. директора)",
            callback_data=f"delegateto_lykov_{task_id}"
        )],
        [InlineKeyboardButton(
            text="👤 Поляков С.Б. (ТБ)",
            callback_data=f"delegateto_polyakov_{task_id}"
        )],
        [InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=f"back_{task_id}"
        )],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================================================================
# SEND APPROVAL REQUEST
# ================================================================

async def send_approval_request(
    bot,
    chat_id: str,
    task_id: str,
    task_title: str,
    task_description: str,
    task_type: str,
    priority: str,
    creator_name: str,
):
    """Send a task approval request with inline buttons to a manager."""
    type_names = {
        "safety": "🦺 Безопасность",
        "procurement": "📦 Снабжение",
        "hr": "👥 Кадры",
        "finance": "💰 Финансы",
        "legal": "📜 Юридический",
        "project_management": "🏗 Управление проектом",
        "reporting": "📊 Отчетность",
        "general": "📌 Общее",
    }

    priority_icons = {
        "P0": "🔴",
        "P1": "🟠",
        "P2": "🟡",
        "P3": "🟢",
    }

    message_text = (
        f"📨 <b>ЗАПРОС НА СОГЛАСОВАНИЕ</b>\n\n"
        f"📋 <b>{task_title}</b>\n"
        f"📂 Тип: {type_names.get(task_type, task_type)}\n"
        f"🚦 Приоритет: {priority_icons.get(priority, '')} {priority}\n"
        f"👤 От: {creator_name}\n\n"
        f"📝 {task_description[:500]}\n\n"
        f"<i>Выберите действие:</i>"
    )

    await bot.send_message(
        chat_id=chat_id,
        text=message_text,
        parse_mode="HTML",
        reply_markup=get_approval_keyboard(task_id),
    )


# ================================================================
# CALLBACK HANDLERS
# ================================================================

@approval_router.callback_query(F.data.startswith("approve_"))
async def handle_approve(callback: CallbackQuery):
    """Handle task approval."""
    task_id = callback.data.replace("approve_", "")
    logger.info(f"Task {task_id} APPROVED by {callback.from_user.full_name}")

    await callback.message.edit_text(
        callback.message.text + "\n\n✅ <b>СОГЛАСОВАНО</b>"
        f"\n👤 {callback.from_user.full_name}",
        parse_mode="HTML",
    )
    await callback.answer("✅ Задача согласована!")

    # TODO: Update task status in DB, notify assignee


@approval_router.callback_query(F.data.startswith("reject_"))
async def handle_reject(callback: CallbackQuery):
    """Handle task rejection."""
    task_id = callback.data.replace("reject_", "")
    logger.info(f"Task {task_id} REJECTED by {callback.from_user.full_name}")

    await callback.message.edit_text(
        callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b>"
        f"\n👤 {callback.from_user.full_name}"
        "\n\n<i>Отправьте причину отклонения следующим сообщением.</i>",
        parse_mode="HTML",
    )
    await callback.answer("❌ Задача отклонена")

    # TODO: Update task status in DB, notify creator


@approval_router.callback_query(F.data.startswith("clarify_"))
async def handle_clarify(callback: CallbackQuery):
    """Handle clarification request."""
    task_id = callback.data.replace("clarify_", "")
    logger.info(f"Task {task_id} CLARIFICATION requested by {callback.from_user.full_name}")

    await callback.message.edit_text(
        callback.message.text + "\n\n❓ <b>ТРЕБУЕТСЯ УТОЧНЕНИЕ</b>"
        f"\n👤 {callback.from_user.full_name}"
        "\n\n<i>Напишите вопрос следующим сообщением.</i>",
        parse_mode="HTML",
    )
    await callback.answer("❓ Запрос на уточнение")

    # TODO: Notify creator about clarification request


@approval_router.callback_query(F.data.startswith("delegate_") & ~F.data.startswith("delegateto_"))
async def handle_delegate(callback: CallbackQuery):
    """Show delegation targets."""
    task_id = callback.data.replace("delegate_", "")

    await callback.message.edit_reply_markup(
        reply_markup=get_delegate_keyboard(task_id)
    )
    await callback.answer("Выберите кому делегировать")


@approval_router.callback_query(F.data.startswith("delegateto_"))
async def handle_delegate_to(callback: CallbackQuery):
    """Handle delegation to specific person."""
    parts = callback.data.split("_")
    target = parts[1]  # zinovieva, lykov, polyakov
    task_id = "_".join(parts[2:])

    target_names = {
        "zinovieva": "Зиновьева А.",
        "lykov": "Лыков М.А.",
        "polyakov": "Поляков С.Б.",
    }

    target_name = target_names.get(target, target)
    logger.info(f"Task {task_id} DELEGATED to {target_name} by {callback.from_user.full_name}")

    await callback.message.edit_text(
        callback.message.text + f"\n\n👉 <b>ДЕЛЕГИРОВАНО: {target_name}</b>"
        f"\n👤 {callback.from_user.full_name}",
        parse_mode="HTML",
    )
    await callback.answer(f"👉 Делегировано: {target_name}")

    # TODO: Reassign task in DB, notify new assignee


@approval_router.callback_query(F.data.startswith("postpone_"))
async def handle_postpone(callback: CallbackQuery):
    """Handle task postponement."""
    task_id = callback.data.replace("postpone_", "")
    logger.info(f"Task {task_id} POSTPONED by {callback.from_user.full_name}")

    await callback.message.edit_text(
        callback.message.text + "\n\n⏸ <b>ОТЛОЖЕНО</b>"
        f"\n👤 {callback.from_user.full_name}"
        "\n\n<i>SLA приостановлен. Задача вернется в очередь.</i>",
        parse_mode="HTML",
    )
    await callback.answer("⏸ Задача отложена, SLA на паузе")

    # TODO: Pause task SLA in DB


@approval_router.callback_query(F.data.startswith("back_"))
async def handle_back(callback: CallbackQuery):
    """Go back to main approval buttons."""
    task_id = callback.data.replace("back_", "")
    await callback.message.edit_reply_markup(
        reply_markup=get_approval_keyboard(task_id)
    )
    await callback.answer()
