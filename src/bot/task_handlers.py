"""
Task management handlers for the Telegram bot.
Implements /newtask, /mytasks, /task commands.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
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
    """Process task description and ask for type."""
    await state.update_data(description=message.text)
    await message.answer(
        "Выберите тип задачи:\n\n"
        "1️⃣ Безопасность (ТБ)\n"
        "2️⃣ Снабжение\n"
        "3️⃣ Кадры (HR)\n"
        "4️⃣ Финансы\n"
        "5️⃣ Юридический\n"
        "6️⃣ Управление проектом\n"
        "7️⃣ Отчетность\n"
        "8️⃣ Общее\n\n"
        "Отправьте номер:"
    )
    await state.set_state(NewTaskStates.waiting_for_type)


@task_router.message(NewTaskStates.waiting_for_type)
async def process_task_type(message: Message, state: FSMContext):
    """Process task type and ask for priority."""
    type_map = {
        "1": "safety",
        "2": "procurement",
        "3": "hr",
        "4": "finance",
        "5": "legal",
        "6": "project_management",
        "7": "reporting",
        "8": "general",
    }
    task_type = type_map.get(message.text.strip(), "general")
    await state.update_data(task_type=task_type)

    await message.answer(
        "Выберите приоритет:\n\n"
        "🔴 P0 — Критический (авария, ЧП)\n"
        "🟠 P1 — Высокий (блокирует работу)\n"
        "🟡 P2 — Средний (стандартная задача)\n"
        "🟢 P3 — Низкий (информационный)\n\n"
        "Отправьте: P0, P1, P2 или P3"
    )
    await state.set_state(NewTaskStates.waiting_for_priority)


@task_router.message(NewTaskStates.waiting_for_priority)
async def process_task_priority(message: Message, state: FSMContext):
    """Process priority and create the task."""
    priority = message.text.strip().upper()
    if priority not in ("P0", "P1", "P2", "P3"):
        priority = "P2"

    data = await state.get_data()
    await state.clear()

    # SLA durations for display
    sla_hours = {"P0": 2, "P1": 8, "P2": 24, "P3": 12}

    type_names = {
        "safety": "Безопасность",
        "procurement": "Снабжение",
        "hr": "Кадры",
        "finance": "Финансы",
        "legal": "Юридический",
        "project_management": "Управление проектом",
        "reporting": "Отчетность",
        "general": "Общее",
    }

    task_type = data.get("task_type", "general")
    description = data.get("description", "")

    # TODO: Actually create task in DB via SLAService
    # For now, confirm to user
    await message.answer(
        f"✅ <b>Задача создана!</b>\n\n"
        f"📋 <b>Описание:</b> {description[:200]}\n"
        f"📂 <b>Тип:</b> {type_names.get(task_type, task_type)}\n"
        f"🚦 <b>Приоритет:</b> {priority}\n"
        f"⏰ <b>SLA:</b> {sla_hours.get(priority, 24)} часов\n\n"
        f"<i>Исполнитель будет назначен автоматически по матрице.</i>"
    )
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
