"""
Memory Service — хранение контекста разговоров в Redis.

Двухуровневая память:
1. Краткосрочная: последние 20 сообщений (точный текст)
2. Долгосрочная: сводка предыдущих разговоров (summarization)

При достижении 20 сообщений — старые сжимаются в сводку через LLM.
"""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime

import redis.asyncio as aioredis

from src.utils.config import settings

logger = logging.getLogger(__name__)

# Настройки
MAX_SHORT_TERM_MESSAGES = 20  # Сколько сообщений хранить в точном виде
SUMMARY_KEY_PREFIX = "memory:summary:"  # Ключ для долгосрочной сводки
HISTORY_KEY_PREFIX = "memory:history:"  # Ключ для краткосрочной истории
HISTORY_TTL = 60 * 60 * 24 * 7  # 7 дней TTL для истории
SUMMARY_TTL = 60 * 60 * 24 * 30  # 30 дней TTL для сводки

# Промпт для сжатия истории в сводку
SUMMARIZE_PROMPT = """Ты — ассистент, который сжимает историю переписки в краткую сводку.
Сохрани ТОЛЬКО важную информацию:
- О чём спрашивал пользователь
- Какие решения были приняты
- Какие объекты/задачи/люди упоминались
- Ключевые факты и цифры

НЕ включай:
- Приветствия и формальности
- Повторяющуюся информацию
- Технические детали работы бота

Формат: краткие пункты, максимум 300 слов.

ИСТОРИЯ ДЛЯ СЖАТИЯ:
{history}"""


class MemoryService:
    """Manages conversation memory with short-term history and long-term summaries."""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None

    async def connect(self):
        """Connect to Redis."""
        if self.redis is None:
            self.redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            logger.info("Memory service connected to Redis")

    async def disconnect(self):
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()

    async def add_message(self, user_id: str, role: str, content: str):
        """
        Add a message to user's conversation history.
        
        Args:
            user_id: Telegram user ID
            role: 'user' or 'assistant'
            content: Message text
        """
        await self.connect()

        key = f"{HISTORY_KEY_PREFIX}{user_id}"

        message = json.dumps({
            "role": role,
            "content": content[:1000],  # Обрезаем слишком длинные сообщения
            "timestamp": datetime.now().isoformat(),
        }, ensure_ascii=False)

        # Добавляем в список
        await self.redis.rpush(key, message)
        await self.redis.expire(key, HISTORY_TTL)

        # Проверяем длину — если больше MAX, нужно сжать
        length = await self.redis.llen(key)
        if length > MAX_SHORT_TERM_MESSAGES * 2:
            # Пора сжимать старые сообщения
            await self._compress_history(user_id)

    async def get_context(self, user_id: str) -> str:
        """
        Get full context for the user: summary + recent messages.
        Returns formatted string for LLM prompt.
        """
        await self.connect()

        # Получаем долгосрочную сводку
        summary = await self._get_summary(user_id)

        # Получаем последние сообщения
        recent = await self._get_recent_messages(user_id)

        if not summary and not recent:
            return ""

        context_parts = []

        if summary:
            context_parts.append(f"СВОДКА ПРЕДЫДУЩИХ РАЗГОВОРОВ:\n{summary}")

        if recent:
            messages_text = []
            for msg in recent:
                role_label = "Пользователь" if msg["role"] == "user" else "Ассистент"
                messages_text.append(f"{role_label}: {msg['content']}")
            context_parts.append(
                f"ПОСЛЕДНИЕ СООБЩЕНИЯ:\n" + "\n".join(messages_text)
            )

        return "\n\n".join(context_parts)

    async def get_messages_for_chat(self, user_id: str) -> List[Dict]:
        """
        Get recent messages in chat format (for Ollama /api/chat).
        Returns list of {"role": "user"/"assistant", "content": "..."}
        """
        await self.connect()

        recent = await self._get_recent_messages(user_id)
        summary = await self._get_summary(user_id)

        messages = []

        # Добавляем сводку как системное сообщение если есть
        if summary:
            messages.append({
                "role": "system",
                "content": f"Контекст предыдущих разговоров с этим пользователем:\n{summary}"
            })

        # Добавляем последние сообщения
        for msg in recent:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        return messages

    async def _get_recent_messages(self, user_id: str) -> List[Dict]:
        """Get last N messages from Redis."""
        key = f"{HISTORY_KEY_PREFIX}{user_id}"

        # Берём последние MAX_SHORT_TERM_MESSAGES
        raw_messages = await self.redis.lrange(key, -MAX_SHORT_TERM_MESSAGES, -1)

        messages = []
        for raw in raw_messages:
            try:
                msg = json.loads(raw)
                messages.append(msg)
            except json.JSONDecodeError:
                continue

        return messages

    async def _get_summary(self, user_id: str) -> Optional[str]:
        """Get long-term summary from Redis."""
        key = f"{SUMMARY_KEY_PREFIX}{user_id}"
        return await self.redis.get(key)

    async def _save_summary(self, user_id: str, summary: str):
        """Save long-term summary to Redis."""
        key = f"{SUMMARY_KEY_PREFIX}{user_id}"
        await self.redis.set(key, summary, ex=SUMMARY_TTL)

    async def _compress_history(self, user_id: str):
        """
        Compress old messages into a summary.
        Keeps last MAX_SHORT_TERM_MESSAGES, summarizes the rest.
        """
        key = f"{HISTORY_KEY_PREFIX}{user_id}"

        # Получаем все сообщения
        all_raw = await self.redis.lrange(key, 0, -1)

        if len(all_raw) <= MAX_SHORT_TERM_MESSAGES:
            return

        # Разделяем: старые (для сжатия) и новые (оставляем)
        old_raw = all_raw[:-MAX_SHORT_TERM_MESSAGES]
        new_raw = all_raw[-MAX_SHORT_TERM_MESSAGES:]

        # Формируем текст старых сообщений для сжатия
        old_messages = []
        for raw in old_raw:
            try:
                msg = json.loads(raw)
                role_label = "Пользователь" if msg["role"] == "user" else "Ассистент"
                old_messages.append(f"{role_label}: {msg['content']}")
            except json.JSONDecodeError:
                continue

        if not old_messages:
            return

        old_text = "\n".join(old_messages)

        # Получаем существующую сводку
        existing_summary = await self._get_summary(user_id)
        if existing_summary:
            old_text = f"ПРЕДЫДУЩАЯ СВОДКА:\n{existing_summary}\n\nНОВЫЕ СООБЩЕНИЯ:\n{old_text}"

        # Сжимаем через LLM (вызываем Ollama напрямую)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_URL}/api/generate",
                    json={
                        "model": "llama3.1:8b",
                        "prompt": SUMMARIZE_PROMPT.format(history=old_text[:4000]),
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    new_summary = resp.json().get("response", "")
                    await self._save_summary(user_id, new_summary)
                    logger.info(f"Compressed history for user {user_id}: {len(old_raw)} messages -> summary")
                else:
                    logger.error(f"Failed to summarize: {resp.status_code}")
                    # Fallback: просто обрезаем без сводки
                    pass
        except Exception as e:
            logger.error(f"Error compressing history: {e}")

        # Обновляем Redis: оставляем только новые сообщения
        await self.redis.delete(key)
        for msg in new_raw:
            await self.redis.rpush(key, msg)
        await self.redis.expire(key, HISTORY_TTL)

    async def clear_history(self, user_id: str):
        """Clear all history for a user."""
        await self.connect()
        await self.redis.delete(f"{HISTORY_KEY_PREFIX}{user_id}")
        await self.redis.delete(f"{SUMMARY_KEY_PREFIX}{user_id}")


# Singleton
memory = MemoryService()
