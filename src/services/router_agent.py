"""
Router Agent — classifies incoming messages and routes to the appropriate agent.
Uses Llama 3.1 8B for fast classification.
"""

import logging
import json
from typing import Optional

from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """Ты — диспетчер AI-системы строительной компании А1. 
Твоя задача — классифицировать входящее сообщение и определить:
1. Тип задачи (task_type)
2. Приоритет (priority)
3. Нужен ли сложный анализ (needs_complex_model)

Типы задач:
- safety: вопросы по технике безопасности, охране труда, СИЗ, каски, ограждения
- procurement: закупки, ТМЦ, материалы, поставщики, цены
- hr: кадры, допуски, медосмотры, отпуска, больничные
- finance: деньги, бюджет, рентабельность, оплата, акты, счета
- legal: договоры, юридические вопросы, иски, претензии, гарантии
- project_management: сроки строительства, графики, объекты, прорабы
- reporting: отчеты, сводки, статистика
- general: общие вопросы, не подходящие под другие категории

Приоритеты:
- P0: аварии, ЧП, угроза жизни
- P1: срочные согласования, блокирующие работу
- P2: стандартные рабочие задачи
- P3: информационные запросы, справки

needs_complex_model = true если вопрос требует глубокого анализа (юридический, финансовый расчет, сложное сравнение). Для простых вопросов = false.

Ответь СТРОГО в формате JSON без пояснений:
{"task_type": "...", "priority": "...", "needs_complex_model": true/false, "summary": "краткое описание запроса в 10 словах"}
"""

# System prompts for each agent type
AGENT_PROMPTS = {
    "general": """Ты — AI-ассистент строительной компании А1. Отвечай кратко, по делу, на русском языке. 
Если не знаешь ответа — скажи об этом честно и предложи обратиться к соответствующему специалисту.""",

    "safety": """Ты — специалист по технике безопасности строительной компании А1. 
Отвечай на вопросы по охране труда, СИЗ, технике безопасности на строительных объектах. 
Ссылайся на СНиП, ГОСТ, ПОТ где применимо. Если вопрос критический (угроза жизни) — подчеркни срочность.""",

    "procurement": """Ты — специалист по снабжению строительной компании А1. 
Помогаешь с заявками на ТМЦ, сравнением цен поставщиков, контролем поставок. 
Отвечай конкретно, с цифрами где возможно.""",

    "hr": """Ты — HR-специалист строительной компании А1. 
Отвечаешь на вопросы по кадрам: допуски, медосмотры, оформление, отпуска, больничные. 
Ссылайся на ТК РФ где применимо.""",

    "finance": """Ты — финансовый аналитик строительной компании А1. 
Помогаешь с расчетами рентабельности, анализом бюджетов, проверкой актов и счетов. 
Давай точные цифры и формулы.""",

    "legal": """Ты — юридический консультант строительной компании А1. 
Анализируешь договоры, выявляешь риски, отвечаешь на юридические вопросы. 
Ссылайся на ГК РФ, ФЗ-44, ФЗ-214 и другие применимые нормы. 
ВАЖНО: для сложных юридических вопросов рекомендуй обратиться к штатному юристу.""",

    "project_management": """Ты — помощник руководителя проекта строительной компании А1. 
Помогаешь с контролем сроков, графиков строительства, координацией между объектами.""",

    "reporting": """Ты — аналитик строительной компании А1. 
Формируешь сводки, отчеты, статистику по объектам. Отвечай структурированно, с таблицами где уместно.""",
}


class RouterAgent:
    """Routes incoming messages to the appropriate agent."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama

    async def classify_message(self, text: str) -> dict:
        """
        Classify the message using Llama 8B (fast).
        Returns: {"task_type": str, "priority": str, "needs_complex_model": bool, "summary": str}
        """
        try:
            response = await self.ollama.generate(
                prompt=text,
                model="llama3.1:8b",
                system_prompt=ROUTER_SYSTEM_PROMPT,
                temperature=0.1,  # Deterministic for classification
            )

            # Parse JSON from response
            # Sometimes LLM wraps JSON in markdown code blocks
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("\n", 1)[1]
                clean_response = clean_response.rsplit("```", 1)[0]

            classification = json.loads(clean_response)
            logger.info(f"Classification: {classification}")
            return classification

        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse classification: {e}. Defaulting to 'general'.")
            return {
                "task_type": "general",
                "priority": "P3",
                "needs_complex_model": False,
                "summary": "Не удалось классифицировать",
            }

    async def process_message(
        self,
        text: str,
        user_id: str,
        user_name: str,
    ) -> str:
        """
        Process a message: classify it, then route to the appropriate agent.

        Args:
            text: User's message text
            user_id: Telegram user ID
            user_name: User's display name

        Returns:
            Agent's response text
        """
        # Step 1: Classify the message
        classification = await self.classify_message(text)
        task_type = classification.get("task_type", "general")
        needs_complex = classification.get("needs_complex_model", False)

        # Step 2: Select model based on complexity
        model = "qwen2.5:32b" if needs_complex else "llama3.1:8b"

        # Step 3: Get the appropriate system prompt
        system_prompt = AGENT_PROMPTS.get(task_type, AGENT_PROMPTS["general"])

        # Step 4: Generate response from the selected agent
        logger.info(
            f"Routing to '{task_type}' agent (model={model}, "
            f"priority={classification.get('priority', 'P3')})"
        )

        response = await self.ollama.generate(
            prompt=text,
            model=model,
            system_prompt=system_prompt,
            temperature=0.4,
        )

        # Step 5: Add classification header (for debugging, can be removed later)
        header = f"<i>[{task_type.upper()} | {classification.get('priority', 'P3')} | {model.split(':')[0]}]</i>\n\n"

        return header + response
