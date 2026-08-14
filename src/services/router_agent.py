"""
Router Agent — classifies incoming messages and routes to the appropriate agent.
Uses Llama 3.1 8B for fast classification.
"""

import logging
import json
from typing import Optional

from src.services.ollama_client import OllamaClient
from src.services.qa_controller import QAController
from src.services.memory_service import memory
from src.services.rag_service import rag_service
from src.agents.secretary import SecretaryAgent
from src.agents.lawyer import LawyerAgent
from src.agents.finance import FinanceAgent
from src.agents.procurement import ProcurementAgent
from src.agents.hr import HRAgent
from src.agents.analyst import AnalystAgent
from src.agents.reporter import ReporterAgent

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """Ты — диспетчер AI-системы строительной компании А1 (ООО «А1»). 
Твоя задача — классифицировать входящее сообщение и определить:
1. Тип задачи (task_type)
2. Приоритет (priority)
3. Нужен ли сложный анализ (needs_complex_model)

КОНТЕКСТ КОМПАНИИ:
А1 — строительная компания, 22 объекта в Москве.
Названия объектов: Михалковская, Дмитровская, Южнопортовая, Нагатинская, Кунцевская и другие.
Если в сообщении упоминается название объекта — это ВСЕГДА task_type: project_management.

Типы задач:
- safety: вопросы по технике безопасности, охране труда, СИЗ, каски, ограждения
- procurement: закупки, ТМЦ, материалы, поставщики, цены, бетон, арматура
- hr: кадры, допуски, медосмотры, отпуска, больничные
- finance: деньги, бюджет, рентабельность, оплата, акты, счета
- legal: договоры, юридические вопросы, иски, претензии, гарантии
- project_management: объекты строительства, сроки, графики, прорабы, статус работ, вопросы по конкретному объекту
- reporting: отчеты, сводки, статистика
- general: общие вопросы, не подходящие под другие категории

ВАЖНО: Если упоминается название объекта (Михалковская, Дмитровская, Южнопортовая, Нагатинская, Кунцевская и т.д.) — это project_management, НЕ general.

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
        self.qa = QAController(ollama)
        # Specialized agents
        self.agents = {
            "safety": None,  # TODO: Safety/Vision agent (Phase 3)
            "procurement": ProcurementAgent(ollama),
            "hr": HRAgent(ollama),
            "finance": FinanceAgent(ollama),
            "legal": LawyerAgent(ollama),
            "project_management": SecretaryAgent(ollama),
            "reporting": ReporterAgent(ollama),
            "general": AnalystAgent(ollama),
        }

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
        Includes conversation memory for context.

        Args:
            text: User's message text
            user_id: Telegram user ID
            user_name: User's display name

        Returns:
            Agent's response text
        """
        # Save user message to memory
        await memory.add_message(user_id, "user", text)

        # Step 1: Classify the message
        classification = await self.classify_message(text)
        task_type = classification.get("task_type", "general")
        needs_complex = classification.get("needs_complex_model", False)

        # Step 2: Route to specialized agent with context
        logger.info(
            f"Routing to '{task_type}' agent "
            f"(priority={classification.get('priority', 'P3')})"
        )

        # Get conversation history for context
        history_messages = await memory.get_messages_for_chat(user_id)

        # Step 2.5: RAG — search knowledge base for relevant context
        rag_context = ""
        try:
            rag_result = rag_service.search(
                query=text,
                agent=task_type if task_type != "general" else None,
                n_results=3,
            )
            if rag_result:
                rag_context = f"\n\n[БАЗА ЗНАНИЙ (используй эту информацию для ответа):\n{rag_result[:3000]}\n]\n\n"
                logger.info(f"RAG: найден контекст ({len(rag_result)} символов)")
        except Exception as e:
            logger.warning(f"RAG search error: {e}")

        agent = self.agents.get(task_type)
        if agent:
            # For agents with process_question — pass context in the question
            context = await memory.get_context(user_id)
            context_prefix = ""
            if context and len(context) > 50:
                context_prefix = f"[КОНТЕКСТ РАЗГОВОРА:\n{context[-2000:]}\n]\n\n"
            response = await agent.process_question(context_prefix + rag_context + text)
        else:
            # Fallback: use chat_with_history for full context
            model = "qwen2.5:32b" if needs_complex else "llama3.1:8b"
            system_prompt = AGENT_PROMPTS.get(task_type, AGENT_PROMPTS["general"])

            # Build messages with history
            messages = [{"role": "system", "content": system_prompt}]
            # Add recent history (last 10 messages for context)
            for msg in history_messages[-10:]:
                messages.append(msg)
            # Add RAG context + current message
            user_content = rag_context + text if rag_context else text
            messages.append({"role": "user", "content": user_content})

            response = await self.ollama.chat_with_history(
                messages=messages,
                model=model,
                temperature=0.4,
            )

        # Step 5: QA Controller — validate response
        approved, reason = await self.qa.validate_response(
            user_question=text,
            agent_response=response,
            task_type=task_type,
        )

        if not approved:
            # Response rejected by QA — return safe fallback
            logger.warning(f"QA rejected response for '{task_type}': {reason}")
            return (
                "⚠️ Система не уверена в точности ответа по вашему вопросу. "
                "Рекомендуем обратиться к специалисту напрямую."
            )

        # Step 6: Build final response
        type_names = {
            "safety": "Безопасность",
            "procurement": "Снабжение",
            "hr": "Кадры",
            "finance": "Финансы",
            "legal": "Юридический",
            "project_management": "Управление проектом",
            "reporting": "Отчетность",
            "general": "Общий вопрос",
        }
        type_ru = type_names.get(task_type, task_type)
        header = f"<i>[{type_ru} | {classification.get('priority', 'P3')}]</i>\n\n"

        # Add disclaimer if QA had concerns
        disclaimer = self.qa.get_disclaimer(reason) if reason else ""

        # Save assistant response to memory
        await memory.add_message(user_id, "assistant", response[:500])

        return header + response + disclaimer
