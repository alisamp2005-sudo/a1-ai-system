"""
Агент: Юрист (Договоры, риски)

Функции:
1. Анализ договоров на риски
2. Ответы на юридические вопросы
3. Интеграция с Яндекс AI Юрист (внешний API)
4. Накопление базы знаний из ответов Яндекса (RAG-обучение)
5. Контроль сроков гарантий и лицензий
"""

import logging
import json
from typing import Optional, Tuple

from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

LAWYER_SYSTEM_PROMPT = """Ты — юридический консультант строительной компании А1.

Твои задачи:
- Анализ договоров подряда, субподряда, поставки
- Выявление рисков и невыгодных условий
- Ответы на юридические вопросы (ГК РФ, ФЗ-214, ФЗ-44, Градостроительный кодекс)
- Проверка сроков гарантий, допусков, лицензий

Правила:
- Всегда указывай ссылки на нормативные акты (статья, пункт)
- Если не уверен — прямо скажи и рекомендуй обратиться к штатному юристу
- Для сложных вопросов рекомендуй консультацию с Яндекс AI Юристом
- Отвечай на русском, профессиональным юридическим языком
"""

CONTRACT_ANALYSIS_PROMPT = """Проанализируй договор/фрагмент договора и выяви:
1. Потенциальные риски для нашей компании (А1 — подрядчик/генподрядчик)
2. Невыгодные условия
3. Отсутствующие важные пункты
4. Несоответствия законодательству

Для каждого риска укажи:
- Уровень: высокий/средний/низкий
- Рекомендация: что изменить

ТЕКСТ ДОГОВОРА/ФРАГМЕНТА:
{text}
"""


class LawyerAgent:
    """Handles legal questions, contract analysis, and Yandex AI integration."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.yandex_enabled = False  # TODO: Enable when API key is provided
        self.rag_enabled = False     # TODO: Enable when ChromaDB collection is ready

    async def process_question(self, question: str) -> str:
        """
        Process a legal question.
        Strategy: RAG first → local model → Yandex AI (if needed).
        """
        # Step 1: Check RAG base (previously answered questions)
        if self.rag_enabled:
            rag_answer = await self._search_rag(question)
            if rag_answer:
                return f"📜 <b>Юридическая консультация</b> <i>(из базы знаний)</i>\n\n{rag_answer}"

        # Step 2: Generate answer with local model
        response = await self.ollama.generate(
            prompt=question,
            model="qwen2.5:32b",  # Legal questions need the powerful model
            system_prompt=LAWYER_SYSTEM_PROMPT,
            temperature=0.3,
        )

        # Step 3: If Yandex is enabled, also query it and save to RAG
        if self.yandex_enabled:
            yandex_answer = await self._query_yandex(question)
            if yandex_answer:
                await self._save_to_rag(question, yandex_answer)
                # Combine both answers
                response += f"\n\n<b>Яндекс AI Юрист:</b>\n{yandex_answer}"

        return f"📜 <b>Юридическая консультация</b>\n\n{response}"

    async def analyze_contract(self, contract_text: str) -> str:
        """Analyze a contract for risks."""
        prompt = CONTRACT_ANALYSIS_PROMPT.format(text=contract_text)

        analysis = await self.ollama.generate(
            prompt=prompt,
            model="qwen2.5:32b",
            system_prompt=LAWYER_SYSTEM_PROMPT,
            temperature=0.2,
        )

        return f"📜 <b>Анализ договора</b>\n\n{analysis}"

    async def _search_rag(self, question: str) -> Optional[str]:
        """Search RAG base for similar previously answered questions."""
        # TODO: Implement ChromaDB search
        return None

    async def _query_yandex(self, question: str) -> Optional[str]:
        """Query Yandex AI Lawyer API."""
        # TODO: Implement when API key is provided
        # API: https://300.ya.ru/api or YandexGPT API
        return None

    async def _save_to_rag(self, question: str, answer: str):
        """Save question-answer pair to RAG base for future use."""
        # TODO: Implement ChromaDB insertion
        logger.info(f"Saved to RAG: Q={question[:50]}...")
