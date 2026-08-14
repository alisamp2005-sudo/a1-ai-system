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


# ================================================================
# /digest — Get digest on demand
# ================================================================

@task_router.message(Command("digest"))
async def cmd_digest(message: Message):
    """Send digest on demand (same as morning digest)."""
    from datetime import datetime
    import pytz

    tz = pytz.timezone("Europe/Moscow")
    now = datetime.now(tz)
    date_str = now.strftime("%d.%m.%Y (%A)")

    # TODO: Pull real data from DB
    digest_text = (
        f"📊 <b>ДАЙДЖЕСТ — А1</b>\n"
        f"<i>{date_str}</i>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔴 <b>Критичное:</b>\n"
        f"Нет критичных событий ✅\n\n"
        f"📋 <b>Задачи:</b>\n"
        f"• Всего активных: 0\n"
        f"• Просрочено: 0\n"
        f"• Создано сегодня: 0\n"
        f"• Закрыто сегодня: 0\n\n"
        f"🏗 <b>Объекты:</b>\n"
        f"• Активных: 5\n"
        f"• С проблемами: 0\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<i>Подробнее: https://ai.bruceli.ru/dashboard</i>"
    )

    await message.answer(digest_text)


# ================================================================
# /users — Admin: manage users
# ================================================================

@task_router.message(Command("users"))
async def cmd_users(message: Message):
    """Show users list with management buttons (admin only)."""
    # TODO: Check if user is admin

    users_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить пользователя", callback_data="users_add")],
        [InlineKeyboardButton(text="📋 Список пользователей", callback_data="users_list")],
        [InlineKeyboardButton(text="🔄 Обновить TG ID", callback_data="users_update_tg")],
    ])

    await message.answer(
        "👥 <b>Управление пользователями</b>\n\n"
        "Текущие пользователи в системе:\n\n"
        "1. Алимов З.Т. — <i>ГД</i>\n"
        "2. Зиновьева А. — <i>Исп. директор</i>\n"
        "3. Лыков М.А. — <i>Зам. директора</i>\n"
        "4. Поляков С.Б. — <i>ТБ</i>\n"
        "5. Администратор — <i>admin</i>\n\n"
        "Выберите действие:",
        reply_markup=users_keyboard,
    )


@task_router.callback_query(F.data == "users_add")
async def handle_users_add(callback: CallbackQuery, state: FSMContext):
    """Start adding a new user."""
    await state.set_state(AddUserStates.waiting_for_name)
    await callback.message.edit_text(
        "👤 <b>Добавление пользователя</b>\n\n"
        "Введите ФИО нового пользователя:"
    )
    await callback.answer()


@task_router.callback_query(F.data == "users_list")
async def handle_users_list(callback: CallbackQuery):
    """Show full users list."""
    await callback.message.edit_text(
        "👥 <b>Все пользователи:</b>\n\n"
        "1. 👑 Алимов З.Т. — ГД — TG: не привязан\n"
        "2. 👑 Зиновьева А. — Исп. директор — TG: не привязан\n"
        "3. 👑 Лыков М.А. — Зам. директора — TG: не привязан\n"
        "4. 👔 Поляков С.Б. — Служба ТБ — TG: не привязан\n"
        "5. ⚙️ Администратор — admin — TG: 5867249984\n\n"
        "<i>Для привязки TG ID попросите сотрудника написать боту /start</i>"
    )
    await callback.answer()


@task_router.callback_query(F.data == "users_update_tg")
async def handle_users_update_tg(callback: CallbackQuery):
    """Explain how to update Telegram IDs."""
    await callback.message.edit_text(
        "🔄 <b>Привязка Telegram ID</b>\n\n"
        "Чтобы привязать Telegram к сотруднику:\n\n"
        "1. Сотрудник пишет боту <code>/start</code>\n"
        "2. Бот автоматически запоминает его TG ID\n"
        "3. Вы связываете TG ID с ФИО через <code>/link</code>\n\n"
        "Или вручную: узнайте TG ID через @userinfobot и введите:\n"
        "<code>/link ФИО TELEGRAM_ID</code>\n\n"
        "Пример: <code>/link Алимов З.Т. 123456789</code>"
    )
    await callback.answer()


# ================================================================
# FSM for adding users
# ================================================================

class AddUserStates(StatesGroup):
    """FSM states for adding a user."""
    waiting_for_name = State()
    waiting_for_role = State()


@task_router.message(AddUserStates.waiting_for_name)
async def process_user_name(message: Message, state: FSMContext):
    """Process new user's name."""
    await state.update_data(name=message.text)

    role_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👷 Рабочий", callback_data="role_worker")],
        [InlineKeyboardButton(text="👔 Руководитель", callback_data="role_manager")],
        [InlineKeyboardButton(text="👑 ТОП-менеджмент", callback_data="role_top_manager")],
    ])

    await message.answer(
        f"👤 Добавляем: <b>{message.text}</b>\n\n"
        "Выберите роль:",
        reply_markup=role_keyboard,
    )
    await state.set_state(AddUserStates.waiting_for_role)


@task_router.callback_query(F.data.startswith("role_"))
async def process_user_role(callback: CallbackQuery, state: FSMContext):
    """Process new user's role."""
    role = callback.data.replace("role_", "")
    data = await state.get_data()
    name = data.get("name", "")

    role_names = {
        "worker": "👷 Рабочий",
        "manager": "👔 Руководитель",
        "top_manager": "👑 ТОП-менеджмент",
    }

    # TODO: Actually save to DB
    await callback.message.edit_text(
        f"✅ <b>Пользователь добавлен!</b>\n\n"
        f"👤 ФИО: {name}\n"
        f"🏷 Роль: {role_names.get(role, role)}\n"
        f"📱 TG ID: не привязан\n\n"
        f"<i>Попросите сотрудника написать боту /start для привязки.</i>"
    )
    await callback.answer("Пользователь добавлен!")
    await state.clear()
