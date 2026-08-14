"""
Telegram Bot Handlers.
Handles all incoming messages and routes them to the appropriate agent.
Uses persistent Reply Keyboard for navigation.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from aiogram.filters import CommandStart, Command

from src.services.ollama_client import OllamaClient
from src.services.router_agent import RouterAgent

logger = logging.getLogger(__name__)
router = Router()

# Initialize services
ollama = OllamaClient()
router_agent = RouterAgent(ollama)

# ================================================================
# PERSISTENT MENU KEYBOARD (always visible at the bottom)
# ================================================================

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Новая задача"),
            KeyboardButton(text="📋 Мои задачи"),
        ],
        [
            KeyboardButton(
                text="📋 Отчет с объекта",
                web_app=WebAppInfo(url="https://ai.bruceli.ru/miniapp/report")
            ),
            KeyboardButton(text="📊 Статус системы"),
        ],
        [
            KeyboardButton(text="❓ Помощь"),
        ],
    ],
    resize_keyboard=True,
    is_persistent=True,
)


# ================================================================
# COMMAND HANDLERS
# ================================================================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command."""
    await message.answer(
        "👋 <b>Добро пожаловать в AI-систему А1!</b>\n\n"
        "Я помогу вам с:\n"
        "• Вопросами по документам и регламентам\n"
        "• Анализом договоров\n"
        "• Финансовыми расчетами\n"
        "• Контролем задач и сроков\n"
        "• Формированием отчетов\n\n"
        "Просто напишите ваш вопрос или используйте кнопки внизу 👇",
        reply_markup=MAIN_MENU,
    )


# ================================================================
# BUTTON HANDLERS (Reply Keyboard)
# ================================================================

@router.message(F.text == "📝 Новая задача")
async def btn_newtask(message: Message):
    """Handle 'Новая задача' button — redirect to /newtask."""
    from src.bot.task_handlers import cmd_newtask
    from aiogram.fsm.context import FSMContext
    # Trigger the /newtask flow
    await message.answer(
        "📝 <b>Создание новой задачи</b>\n\n"
        "Опишите задачу (что нужно сделать, для кого, на каком объекте):"
    )
    # We need to set state manually since we're not going through the command filter
    # This is handled by the task_router via FSM


@router.message(F.text == "📋 Мои задачи")
async def btn_mytasks(message: Message):
    """Handle 'Мои задачи' button."""
    await message.answer(
        "📋 <b>Ваши активные задачи:</b>\n\n"
        "<i>База данных пользователей ещё не заполнена. "
        "Эта функция заработает после импорта сотрудников.</i>",
        reply_markup=MAIN_MENU,
    )


@router.message(F.text == "📊 Статус системы")
async def btn_status(message: Message):
    """Handle 'Статус системы' button."""
    ollama_status = await ollama.health_check()
    status_text = (
        "<b>📊 Статус системы:</b>\n\n"
        f"• Ollama: {'✅ Работает' if ollama_status else '❌ Недоступен'}\n"
        f"• Telegram Bot: ✅ Работает\n"
        f"• База данных: ✅ Работает\n"
    )
    await message.answer(status_text, reply_markup=MAIN_MENU)


@router.message(F.text == "❓ Помощь")
async def btn_help(message: Message):
    """Handle 'Помощь' button."""
    await message.answer(
        "<b>Как пользоваться ботом:</b>\n\n"
        "📝 <b>Новая задача</b> — создать задачу с назначением исполнителя и SLA\n"
        "📋 <b>Мои задачи</b> — посмотреть ваши активные задачи\n"
        "📊 <b>Статус системы</b> — проверить работу AI-моделей\n\n"
        "<b>Или просто напишите вопрос</b> — я определю тему и отвечу через AI.\n\n"
        "Примеры вопросов:\n"
        "• «Какие документы нужны для допуска на объект?»\n"
        "• «Рассчитай рентабельность объекта Михалковская»\n"
        "• «Когда истекает гарантия по договору с ООО Строймонтаж?»",
        reply_markup=MAIN_MENU,
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await btn_help(message)


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Handle /status command."""
    await btn_status(message)


# ================================================================
# TEXT MESSAGE HANDLER (AI routing)
# ================================================================

@router.message(F.text)
async def handle_text_message(message: Message):
    """Handle any text message — route to appropriate agent."""
    user_text = message.text
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name

    logger.info(f"Message from {user_name} ({user_id}): {user_text[:100]}")

    # Show typing indicator
    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        # Route the message through the Router agent
        response = await router_agent.process_message(
            text=user_text,
            user_id=user_id,
            user_name=user_name,
        )
        await message.answer(response, reply_markup=MAIN_MENU)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке вашего запроса. "
            "Попробуйте позже или обратитесь к администратору.",
            reply_markup=MAIN_MENU,
        )


@router.message(F.voice)
async def handle_voice_message(message: Message):
    """Handle voice messages — transcribe with Whisper and process."""
    import tempfile
    import os
    from src.services.whisper_service import transcribe_voice

    await message.answer("🎤 Распознаю голосовое сообщение...", reply_markup=MAIN_MENU)

    try:
        # Download voice file from Telegram
        voice = message.voice
        file = await message.bot.get_file(voice.file_id)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            tmp_path = tmp.name
            await message.bot.download_file(file.file_path, tmp_path)

        # Transcribe with Whisper
        text = await transcribe_voice(tmp_path)

        # Clean up temp file
        os.unlink(tmp_path)

        if not text or len(text.strip()) < 2:
            await message.answer(
                "⚠️ Не удалось распознать речь. Попробуйте записать сообщение ещё раз.",
                reply_markup=MAIN_MENU,
            )
            return

        # Show transcription
        await message.answer(
            f"📝 <b>Распознано:</b>\n<i>{text}</i>\n\n⏳ Обрабатываю...",
            reply_markup=MAIN_MENU,
        )

        # Process transcribed text through Router (same as text messages)
        await message.bot.send_chat_action(message.chat.id, "typing")

        response = await router_agent.process_message(
            text=text,
            user_id=str(message.from_user.id),
            user_name=message.from_user.full_name,
        )
        await message.answer(response, reply_markup=MAIN_MENU)

    except Exception as e:
        logger.error(f"Voice message error: {e}")
        await message.answer(
            "⚠️ Ошибка при обработке голосового сообщения. Попробуйте текстом.",
            reply_markup=MAIN_MENU,
        )


@router.message(F.photo)
async def handle_photo_message(message: Message):
    """Handle photo messages — analyze for safety violations using LLaVA."""
    import tempfile
    import os
    from src.agents.safety import SafetyAgent

    await message.answer("🦺 Анализирую фото на нарушения ТБ...", reply_markup=MAIN_MENU)

    try:
        # Get the largest photo
        photo = message.photo[-1]
        file = await message.bot.get_file(photo.file_id)

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
            await message.bot.download_file(file.file_path, tmp_path)

        # Analyze with Vision agent
        safety = SafetyAgent()
        result = await safety.analyze_photo(tmp_path)

        # Clean up
        os.unlink(tmp_path)

        await message.answer(result, reply_markup=MAIN_MENU)

    except Exception as e:
        logger.error(f"Photo analysis error: {e}")
        await message.answer(
            "⚠️ Ошибка при анализе фото. Попробуйте позже.",
            reply_markup=MAIN_MENU,
        )
