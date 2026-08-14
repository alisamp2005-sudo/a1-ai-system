"""
Агент: Снабженец (Заявки ТМЦ, сравнение цен)

Функции:
1. Формирование заявок на ТМЦ
2. Сравнение цен поставщиков
3. Контроль поставок
4. Рекомендации по закупкам
"""

import logging
from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

PROCUREMENT_SYSTEM_PROMPT = """Ты — специалист по снабжению строительной компании А1.

Твои задачи:
- Помощь в формировании заявок на ТМЦ (товарно-материальные ценности)
- Сравнение цен поставщиков
- Контроль сроков поставок
- Рекомендации по оптимизации закупок
- Расчет потребности в материалах

Правила:
- Всегда уточняй объект, для которого нужны материалы
- Указывай единицы измерения (м³, тонны, штуки, м.п.)
- Если знаешь типичные цены — указывай диапазон
- Для крупных закупок рекомендуй запросить 3+ коммерческих предложения
- Учитывай логистику (доставка на объект)
"""


class ProcurementAgent:
    """Handles procurement requests, price comparisons, and supply tracking."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def process_question(self, question: str) -> str:
        """Process a procurement question."""
        response = await self.ollama.generate(
            prompt=question,
            model="llama3.1:8b",  # Simple procurement questions
            system_prompt=PROCUREMENT_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return f"📦 <b>Снабжение</b>\n\n{response}"

    async def create_request(self, items_description: str, project_name: str = "") -> str:
        """Help create a procurement request."""
        prompt = (
            f"Помоги сформировать заявку на ТМЦ.\n"
            f"Объект: {project_name}\n"
            f"Что нужно: {items_description}\n\n"
            f"Сформируй заявку в формате таблицы: "
            f"Наименование | Ед.изм. | Кол-во | Примечание"
        )

        response = await self.ollama.generate(
            prompt=prompt,
            model="qwen2.5:32b",  # Structured output needs better model
            system_prompt=PROCUREMENT_SYSTEM_PROMPT,
            temperature=0.2,
        )

        return f"📦 <b>Заявка на ТМЦ</b> ({project_name})\n\n{response}"
