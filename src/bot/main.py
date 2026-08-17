"""
A1 AI System — Telegram Bot (aiogram 3)
Main entry point for the bot.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from src.bot.handlers import router as handlers_router
from src.bot.task_handlers import task_router
from src.bot.approval_handlers import approval_router
from src.bot.document_handlers import document_router
from src.bot.document_delivery_handlers import document_delivery_router
from src.utils.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Start the bot."""
    if not settings.TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN is not set in .env!")
        return

    # Use local Telegram Bot API server if available (supports files up to 2GB)
    local_api_url = os.getenv("TELEGRAM_LOCAL_API_URL", "")
    session = None
    if local_api_url:
        local_server = TelegramAPIServer.from_base(local_api_url)
        session = AiohttpSession(api=local_server)
        logger.info(f"Using LOCAL Telegram Bot API: {local_api_url}")
    else:
        logger.info("Using standard Telegram Bot API (file limit: 20MB)")

    bot = Bot(
        token=settings.TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher()

    # Register handlers
    dp.include_router(approval_router)
    dp.include_router(task_router)
    dp.include_router(document_router)
    dp.include_router(document_delivery_router)
    dp.include_router(handlers_router)

    logger.info("Bot is starting...")
    logger.info(f"Ollama URL: {settings.OLLAMA_URL}")

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
