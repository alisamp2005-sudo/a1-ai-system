"""
Агент: HR (Кадры, допуски, медосмотры)

Функции:
1. Контроль сроков допусков и удостоверений
2. Контроль медосмотров
3. Ответы по ТК РФ (отпуска, больничные, увольнение)
4. Оформление документов
"""

import logging
from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

HR_SYSTEM_PROMPT = """Ты — HR-специалист строительной компании А1.

Твои задачи:
- Контроль сроков допусков к работам (высотные, электро, газо)
- Контроль медицинских осмотров (периодические, предварительные)
- Ответы на вопросы по Трудовому кодексу РФ
- Помощь с оформлением кадровых документов
- Расчет отпусков, больничных

Правила:
- Ссылайся на конкретные статьи ТК РФ
- Для допусков указывай сроки действия (обычно 1 год для ОТ, 3 года для электро)
- Медосмотры: предварительный (при приеме), периодический (1 раз в год для строителей)
- Если вопрос сложный — рекомендуй обратиться к кадровику
"""


class HRAgent:
    """Handles HR questions, permits, medical exams tracking."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def process_question(self, question: str) -> str:
        """Process an HR question."""
        response = await self.ollama.generate(
            prompt=question,
            model="llama3.1:8b",  # Most HR questions are straightforward
            system_prompt=HR_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return f"👥 <b>Кадры</b>\n\n{response}"

    async def check_permits_status(self, employee_name: str) -> str:
        """Check permit/certification status for an employee."""
        # TODO: Query database for actual permit data
        prompt = (
            f"Какие допуски и удостоверения обычно нужны строительному рабочему? "
            f"Перечисли с указанием сроков действия и порядка продления."
        )

        response = await self.ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",
            system_prompt=HR_SYSTEM_PROMPT,
            temperature=0.3,
        )

        return f"👥 <b>Допуски: {employee_name}</b>\n\n{response}"
