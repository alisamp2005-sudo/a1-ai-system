"""
A1 AI System — Telegram Bot (aiogram 3)
Main entry point for the bot.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.bot.handlers import router as handlers_router
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

    bot = Bot(
        token=settings.TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Register handlers
    dp.include_router(handlers_router)

    logger.info("Bot is starting...")
    logger.info(f"Ollama URL: {settings.OLLAMA_URL}")

    # Start polling
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
