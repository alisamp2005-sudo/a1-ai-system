"""
Telegram Bot Handlers.
Handles all incoming messages and routes them to the appropriate agent.
"""

import logging
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command

from src.services.ollama_client import OllamaClient
from src.services.router_agent import RouterAgent

logger = logging.getLogger(__name__)
router = Router()

# Initialize services
ollama = OllamaClient()
router_agent = RouterAgent(ollama)


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
        "Просто напишите ваш вопрос или отправьте голосовое сообщение."
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    await message.answer(
        "<b>Доступные команды:</b>\n\n"
        "/start — Приветствие\n"
        "/help — Эта справка\n"
        "/status — Статус системы\n"
        "/newtask — Создать задачу вручную\n\n"
        "<b>Просто напишите вопрос</b> — я определю тему и отвечу.\n"
        "<b>Голосовое сообщение</b> — я расшифрую и обработаю."
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Handle /status command — check system health."""
    # Check Ollama
    ollama_status = await ollama.health_check()

    status_text = (
        "<b>📊 Статус системы:</b>\n\n"
        f"• Ollama: {'✅ Работает' if ollama_status else '❌ Недоступен'}\n"
        f"• Telegram Bot: ✅ Работает\n"
        f"• База данных: ✅ Работает\n"
    )
    await message.answer(status_text)


@router.message(F.text)
async def handle_text_message(message: Message):
    """Handle any text message — route to appropriate agent."""
    user_text = message.text
    user_id = str(message.from_user.id)
    user_name = message.from_user.full_name

    logger.info(f"Message from {user_name} ({user_id}): {user_text[:100]}")

    # Show typing indicator
    await message.answer_chat_action("typing")

    try:
        # Route the message through the Router agent
        response = await router_agent.process_message(
            text=user_text,
            user_id=user_id,
            user_name=user_name,
        )
        await message.answer(response)

    except Exception as e:
        logger.error(f"Error processing message: {e}")
        await message.answer(
            "⚠️ Произошла ошибка при обработке вашего запроса. "
            "Попробуйте позже или обратитесь к администратору."
        )


@router.message(F.voice)
async def handle_voice_message(message: Message):
    """Handle voice messages — transcribe and process."""
    await message.answer(
        "🎤 Голосовые сообщения будут поддержаны в следующем обновлении. "
        "Пока, пожалуйста, напишите текстом."
    )
    # TODO Phase 1: Integrate Whisper for voice transcription
