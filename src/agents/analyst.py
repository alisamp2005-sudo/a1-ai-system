"""
Агент: Аналитик (База знаний — СНиП, ГОСТ, регламенты)

Функции:
1. Ответы на вопросы по регламентам компании
2. Поиск по СНиП, ГОСТ, СП
3. Разъяснение нормативных требований
4. Помощь сотрудникам "как сделать X"
"""

import logging
from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

ANALYST_SYSTEM_PROMPT = """Ты — аналитик-консультант строительной компании А1.
Ты обучен на внутренних регламентах компании, СНиП, ГОСТ и СП.

Твои задачи:
- Отвечать на вопросы сотрудников "как сделать X" по регламентам
- Разъяснять требования нормативных документов
- Помогать найти нужный СНиП/ГОСТ/СП
- Давать пошаговые инструкции по процедурам

Правила:
- Если знаешь конкретный номер СНиП/ГОСТ — указывай его
- Если не уверен в номере — скажи "рекомендую уточнить в актуальной редакции"
- Отвечай пошагово, структурированно
- Если вопрос выходит за рамки твоих знаний — направь к руководителю
"""


class AnalystAgent:
    """Answers questions from knowledge base (regulations, SNiP, GOST)."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.rag_enabled = False  # TODO: Enable when ChromaDB is populated

    async def process_question(self, question: str) -> str:
        """Process a knowledge base question."""
        # Step 1: Search RAG (when enabled)
        context = ""
        if self.rag_enabled:
            context = await self._search_knowledge_base(question)

        # Step 2: Generate answer
        prompt = question
        if context:
            prompt = (
                f"Контекст из базы знаний:\n{context}\n\n"
                f"Вопрос пользователя: {question}\n\n"
                f"Ответь на основе контекста. Если контекст не содержит ответа — "
                f"используй свои знания, но предупреди об этом."
            )

        response = await self.ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",  # Fast model for knowledge base lookups
            system_prompt=ANALYST_SYSTEM_PROMPT,
            temperature=0.3,
        )

        source_note = " <i>(из базы знаний)</i>" if context else ""
        return f"📚 <b>Справка{source_note}</b>\n\n{response}"

    async def _search_knowledge_base(self, query: str) -> str:
        """Search ChromaDB for relevant documents."""
        # TODO: Implement ChromaDB search
        # Will search across: SNiP, GOST, company regulations, procedures
        return ""
