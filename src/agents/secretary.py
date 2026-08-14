"""
Агент: Секретарь (Протоколы совещаний)

Функции:
1. Извлечение задач из текста/аудио совещания
2. Формирование протокола совещания
3. Создание задач с дедлайнами и исполнителями
4. Отправка протокола участникам
"""

import logging
import json
from typing import List, Dict, Optional

from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

SECRETARY_SYSTEM_PROMPT = """Ты — AI-секретарь строительной компании А1. 
Твоя задача — обрабатывать текст совещаний и извлекать из них:
1. Ключевые решения
2. Задачи с исполнителями и сроками
3. Вопросы, оставшиеся открытыми

Правила:
- Если исполнитель не назван явно — пиши "Не назначен"
- Если срок не назван — пиши "Не определен"
- Формулируй задачи конкретно и измеримо
- Пиши на русском языке, профессионально
"""

EXTRACT_TASKS_PROMPT = """Проанализируй текст совещания и извлеки ВСЕ задачи/поручения.

Для каждой задачи определи:
- description: что нужно сделать (конкретно)
- assignee: кому поручено (ФИО или должность)
- deadline: срок выполнения (дата или "не определен")
- priority: P0/P1/P2/P3

Ответь в формате JSON:
{"tasks": [{"description": "...", "assignee": "...", "deadline": "...", "priority": "P2"}], "decisions": ["решение 1", "решение 2"], "open_questions": ["вопрос 1"]}

ТЕКСТ СОВЕЩАНИЯ:
{text}
"""

PROTOCOL_PROMPT = """Сформируй протокол совещания на основе текста.

Формат протокола:
1. Дата и участники (если указаны)
2. Повестка дня
3. Принятые решения
4. Поручения (задача / исполнитель / срок)
5. Открытые вопросы

Пиши кратко, по делу, в деловом стиле.

ТЕКСТ СОВЕЩАНИЯ:
{text}
"""


class SecretaryAgent:
    """Processes meeting texts, extracts tasks, generates protocols."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def process_question(self, question: str) -> str:
        """
        Router-compatible entry point: process any project management question.
        If it looks like a meeting text — generate protocol.
        Otherwise — answer as project management assistant.
        """
        # Check if this is a meeting transcript (long text with dialogue)
        if len(question) > 500 and any(kw in question.lower() for kw in ["совещани", "протокол", "решили", "поручить"]):
            return await self.generate_protocol(question)

        # Otherwise — answer as project management assistant
        prompt = question
        response = await self.ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",
            system_prompt=(
                "Ты — помощник руководителя проекта строительной компании А1. "
                "Помогаешь с контролем сроков, графиков строительства, "
                "координацией между объектами, информацией о текущих проектах. "
                "Отвечай кратко и по делу на русском языке. "
                "Текущие объекты компании: Михалковская, Дмитровская, Южнопортовая, "
                "Нагатинская, Кунцевская (это тестовые данные, уточни у руководства)."
            ),
            temperature=0.4,
        )
        return response

    async def process_meeting_text(self, text: str) -> str:
        """
        Process meeting text and return formatted protocol.
        """
        # Generate protocol
        protocol = await self.generate_protocol(text)
        return protocol

    async def extract_tasks(self, text: str) -> Dict:
        """
        Extract tasks from meeting text as structured data.
        Returns dict with tasks, decisions, and open questions.
        """
        prompt = EXTRACT_TASKS_PROMPT.format(text=text)

        response = await self.ollama.generate(
            prompt=prompt,
            model="qwen2.5:32b",  # Complex task — use powerful model
            system_prompt=SECRETARY_SYSTEM_PROMPT,
            temperature=0.2,
        )

        try:
            # Clean and parse JSON
            clean = response.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]
            return json.loads(clean)
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse tasks JSON: {e}")
            return {"tasks": [], "decisions": [], "open_questions": [], "raw": response}

    async def generate_protocol(self, text: str) -> str:
        """
        Generate a formatted meeting protocol.
        """
        prompt = PROTOCOL_PROMPT.format(text=text)

        protocol = await self.ollama.generate(
            prompt=prompt,
            model="qwen2.5:32b",  # Complex task
            system_prompt=SECRETARY_SYSTEM_PROMPT,
            temperature=0.3,
        )

        return f"📋 <b>ПРОТОКОЛ СОВЕЩАНИЯ</b>\n\n{protocol}"

    async def summarize_meeting(self, text: str) -> str:
        """
        Quick summary of a meeting (for notifications).
        """
        prompt = (
            f"Кратко (3-5 предложений) опиши итоги совещания:\n\n{text}"
        )

        summary = await self.ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",  # Simple task — fast model
            system_prompt=SECRETARY_SYSTEM_PROMPT,
            temperature=0.3,
        )

        return summary
