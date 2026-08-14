"""
Агент: Финансист (Расчеты, бюджеты, рентабельность)

Функции:
1. Расчет рентабельности объектов
2. Анализ бюджетов и отклонений
3. Проверка актов и счетов
4. Формирование финансовых сводок
"""

import logging
from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

FINANCE_SYSTEM_PROMPT = """Ты — финансовый аналитик строительной компании А1.

Твои задачи:
- Расчет рентабельности строительных объектов
- Анализ бюджетов (план/факт)
- Проверка корректности актов КС-2, КС-3
- Расчет себестоимости работ
- Анализ дебиторской/кредиторской задолженности
- Формирование финансовых отчетов

Правила:
- Всегда показывай формулы расчета
- Давай конкретные цифры, не общие слова
- Если данных недостаточно — запроси конкретные цифры
- Используй профессиональную финансовую терминологию
- Рентабельность = (Выручка - Себестоимость) / Выручка × 100%
"""


class FinanceAgent:
    """Handles financial calculations, budgets, and profitability analysis."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def process_question(self, question: str) -> str:
        """Process a financial question."""
        response = await self.ollama.generate(
            prompt=question,
            model="qwen2.5:32b",  # Financial calculations need precision
            system_prompt=FINANCE_SYSTEM_PROMPT,
            temperature=0.2,  # Low temperature for accuracy
        )
        return f"💰 <b>Финансовый анализ</b>\n\n{response}"

    async def calculate_profitability(
        self, revenue: float, cost: float, project_name: str = ""
    ) -> str:
        """Calculate project profitability."""
        profit = revenue - cost
        margin = (profit / revenue * 100) if revenue > 0 else 0

        prompt = (
            f"Рассчитай рентабельность объекта {project_name}:\n"
            f"Выручка: {revenue:,.0f} руб.\n"
            f"Себестоимость: {cost:,.0f} руб.\n"
            f"Прибыль: {profit:,.0f} руб.\n"
            f"Маржинальность: {margin:.1f}%\n\n"
            f"Дай оценку: это нормальная рентабельность для строительства? "
            f"Какие рекомендации?"
        )

        response = await self.ollama.generate(
            prompt=prompt,
            model="qwen2.5:32b",
            system_prompt=FINANCE_SYSTEM_PROMPT,
            temperature=0.3,
        )

        return (
            f"💰 <b>Рентабельность: {project_name}</b>\n\n"
            f"📊 Выручка: {revenue:,.0f} ₽\n"
            f"📊 Себестоимость: {cost:,.0f} ₽\n"
            f"📊 Прибыль: {profit:,.0f} ₽\n"
            f"📊 Маржа: {margin:.1f}%\n\n"
            f"{response}"
        )
