"""
Агент: Сводчик (Утренний дайджест, отчетность)

Функции:
1. Формирование утреннего дайджеста для ГД
2. Сводка по всем объектам
3. Агрегация данных из разных источников
4. Статистика по задачам и просрочкам
"""

import logging
from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

REPORTER_SYSTEM_PROMPT = """Ты — аналитик-сводчик строительной компании А1.

Твои задачи:
- Формирование ежедневных сводок для руководства
- Агрегация информации по всем 22 объектам
- Выявление проблемных зон (просрочки, отклонения)
- Краткие и информативные отчеты

Правила:
- Пиши кратко, по делу — руководитель читает за 2 минуты
- Используй структуру: объект → статус → проблемы → действия
- Выделяй критичное (просрочки, аварии) в начале
- Цифры и факты, не воду
"""


class ReporterAgent:
    """Generates daily digests and summary reports."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def process_question(self, question: str) -> str:
        """Process a reporting question."""
        response = await self.ollama.generate(
            prompt=question,
            model="llama3.1:8b",
            system_prompt=REPORTER_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return f"📊 <b>Отчетность</b>\n\n{response}"

    async def generate_daily_digest(self) -> str:
        """
        Generate morning digest for top management.
        TODO: Pull real data from DB (tasks, SLA breaches, project statuses).
        """
        # TODO: Query database for:
        # - Active tasks count by status
        # - SLA breaches in last 24h
        # - New tasks created
        # - Projects with issues

        prompt = (
            "Сформируй шаблон утреннего дайджеста для генерального директора "
            "строительной компании с 22 объектами. "
            "Включи разделы: критичное, задачи на сегодня, статус объектов, финансы."
        )

        response = await self.ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",
            system_prompt=REPORTER_SYSTEM_PROMPT,
            temperature=0.4,
        )

        return f"📊 <b>УТРЕННИЙ ДАЙДЖЕСТ</b>\n\n{response}"

    async def generate_project_summary(self, project_name: str) -> str:
        """Generate summary for a specific project."""
        # TODO: Pull real data from DB
        prompt = (
            f"Сформируй краткую сводку по строительному объекту '{project_name}'. "
            f"Включи: этап работ, % готовности, проблемы, ближайшие дедлайны."
        )

        response = await self.ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",
            system_prompt=REPORTER_SYSTEM_PROMPT,
            temperature=0.3,
        )

        return f"📊 <b>Сводка: {project_name}</b>\n\n{response}"
