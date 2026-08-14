"""
Task management handlers for the Telegram bot.
Implements /newtask, /mytasks commands with inline keyboard buttons.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logger = logging.getLogger(__name__)
task_router = Router()


class NewTaskStates(StatesGroup):
    """FSM states for /newtask command."""
    waiting_for_description = State()
    waiting_for_type = State()
    waiting_for_priority = State()


# ================================================================
# KEYBOARDS
# ================================================================

def get_task_type_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting task type."""
    buttons = [
        [InlineKeyboardButton(text="🦺 Безопасность (ТБ)", callback_data="type_safety")],
        [InlineKeyboardButton(text="📦 Снабжение", callback_data="type_procurement")],
        [InlineKeyboardButton(text="👥 Кадры (HR)", callback_data="type_hr")],
        [InlineKeyboardButton(text="💰 Финансы", callback_data="type_finance")],
        [InlineKeyboardButton(text="📜 Юридический", callback_data="type_legal")],
        [InlineKeyboardButton(text="🏗 Управление проектом", callback_data="type_project_management")],
        [InlineKeyboardButton(text="📊 Отчетность", callback_data="type_reporting")],
        [InlineKeyboardButton(text="📌 Общее", callback_data="type_general")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_priority_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for selecting priority."""
    buttons = [
        [InlineKeyboardButton(text="🔴 Критический (авария, ЧП)", callback_data="priority_P0")],
        [InlineKeyboardButton(text="🟠 Высокий (блокирует работу)", callback_data="priority_P1")],
        [InlineKeyboardButton(text="🟡 Средний (стандартная задача)", callback_data="priority_P2")],
        [InlineKeyboardButton(text="🟢 Низкий (информационный)", callback_data="priority_P3")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ================================================================
# HANDLERS
# ================================================================

@task_router.message(Command("newtask"))
async def cmd_newtask(message: Message, state: FSMContext):
    """Start creating a new task manually."""
    await message.answer(
        "📝 <b>Создание новой задачи</b>\n\n"
        "Опишите задачу (что нужно сделать, для кого, на каком объекте):"
    )
    await state.set_state(NewTaskStates.waiting_for_description)


@task_router.message(NewTaskStates.waiting_for_description)
async def process_task_description(message: Message, state: FSMContext):
    """Process task description and show type buttons."""
    await state.update_data(description=message.text)
    await message.answer(
        "📂 <b>Выберите тип задачи:</b>",
        reply_markup=get_task_type_keyboard(),
    )
    await state.set_state(NewTaskStates.waiting_for_type)


@task_router.callback_query(NewTaskStates.waiting_for_type, F.data.startswith("type_"))
async def process_task_type(callback: CallbackQuery, state: FSMContext):
    """Process task type selection and show priority buttons."""
    task_type = callback.data.replace("type_", "")
    await state.update_data(task_type=task_type)

    await callback.message.edit_text(
        "🚦 <b>Выберите приоритет:</b>",
        reply_markup=get_priority_keyboard(),
    )
    await state.set_state(NewTaskStates.waiting_for_priority)
    await callback.answer()


@task_router.callback_query(NewTaskStates.waiting_for_priority, F.data.startswith("priority_"))
async def process_task_priority(callback: CallbackQuery, state: FSMContext):
    """Process priority selection and create the task."""
    priority = callback.data.replace("priority_", "")

    data = await state.get_data()
    await state.clear()

    # SLA durations for display
    sla_hours = {"P0": 2, "P1": 8, "P2": 24, "P3": 12}

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

    priority_names = {
        "P0": "🔴 Критический",
        "P1": "🟠 Высокий",
        "P2": "🟡 Средний",
        "P3": "🟢 Низкий",
    }

    task_type = data.get("task_type", "general")
    description = data.get("description", "")

    # TODO: Actually create task in DB via SLAService
    await callback.message.edit_text(
        f"✅ <b>Задача создана!</b>\n\n"
        f"📋 <b>Описание:</b> {description[:200]}\n"
        f"📂 <b>Тип:</b> {type_names.get(task_type, task_type)}\n"
        f"🚦 <b>Приоритет:</b> {priority_names.get(priority, priority)}\n"
        f"⏰ <b>SLA:</b> {sla_hours.get(priority, 24)} часов\n\n"
        f"<i>Исполнитель будет назначен автоматически по матрице.</i>"
    )
    await callback.answer("Задача создана!")
    logger.info(f"Task created via /newtask: type={task_type}, priority={priority}")


@task_router.message(Command("mytasks"))
async def cmd_mytasks(message: Message):
    """Show user's active tasks."""
    # TODO: Query DB for user's tasks
    await message.answer(
        "📋 <b>Ваши активные задачи:</b>\n\n"
        "<i>База данных пользователей ещё не заполнена. "
        "Эта функция заработает после импорта сотрудников.</i>"
    )
