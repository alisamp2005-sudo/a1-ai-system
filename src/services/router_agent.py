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
from src.services.db_context import db_context
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
А1 — строительная компания с 16 активными объектами.
Если в сообщении упоминается конкретный объект, стройплощадка, адрес или слово "объект/объекты" — это ВСЕГДА task_type: project_management.
Слова-маркеры для project_management: объект, объекты, стройка, площадка, прораб, Остров, ЩЛЗ, Кубинка, Ленская, Михалковская, ДРОЗ, Алые паруса, ЛДМ, ВСК, реновация, Житная, Мосводосток, Дмитровское.

Типы задач:
- safety: вопросы по технике безопасности, охране труда, СИЗ, каски, ограждения
- procurement: закупки, ТМЦ, материалы, поставщики, цены, бетон, арматура
- hr: кадры, допуски, медосмотры, отпуска, больничные
- finance: деньги, бюджет, рентабельность, оплата, акты, счета
- legal: договоры, юридические вопросы, иски, претензии, гарантии
- project_management: объекты строительства, сроки, графики, прорабы, статус работ, вопросы по конкретному объекту
- reporting: отчеты, сводки, статистика
- general: общие вопросы, не подходящие под другие категории

ВАЖНО: Вопросы про объекты, стройки, площадки — это ВСЕГДА project_management, НИКОГДА не general.

Приоритеты:
- P0: аварии, ЧП, угроза жизни
- P1: срочные согласования, блокирующие работу
- P2: стандартные рабочие задачи
- P3: информационные запросы, справки

needs_complex_model = true если вопрос требует глубокого анализа (юридический, финансовый расчет, сложное сравнение). Для простых вопросов = false.

Ответь СТРОГО в формате JSON без пояснений:
{"task_type": "...", "priority": "...", "needs_complex_model": true/false, "summary": "краткое описание запроса в 10 словах"}
"""

# Anti-hallucination base instruction (added to all agents)
_NO_HALLUCINATION = """\n\nКРИТИЧЕСКИ ВАЖНО:
- Если ты НЕ ЗНАЕШЬ точного ответа — прямо скажи: «У меня нет данных по этому вопросу».
- НИКОГДА не выдумывай факты, цифры, адреса, даты, имена, цены.
- Если в [БАЗА ЗНАНИЙ] есть релевантная информация — используй ТОЛЬКО её.
- Если информации недостаточно — скажи что нужно уточнить и у кого.
- Отвечай КРАТКО и ПО ДЕЛУ. Не лей воду.
- Язык: только русский."""

# System prompts for each agent type
AGENT_PROMPTS = {
    "general": f"""Ты — AI-ассистент строительной компании А1 (ООО «А1», Москва, 22 строительных объекта).
Отвечай кратко, по делу. Если вопрос не относится к строительству или компании — скажи об этом.
Если не знаешь ответа — честно скажи и предложи обратиться к конкретному специалисту.{_NO_HALLUCINATION}""",

    "safety": f"""Ты — специалист по технике безопасности строительной компании А1.
Отвечай на вопросы по охране труда, СИЗ, ТБ на строительных объектах.
Ссылайся на конкретные нормативы: Приказ Минтруда №883н, №782н, СНиП 12-03-2001, ГОСТ 12.x.
Если вопрос критический (угроза жизни) — подчеркни СРОЧНОСТЬ и укажи немедленные действия.
Не выдумывай номера пунктов и статей — используй только те, что есть в [БАЗА ЗНАНИЙ].{_NO_HALLUCINATION}""",

    "procurement": f"""Ты — специалист по снабжению строительной компании А1.
Помогаешь с заявками на ТМЦ, подбором материалов, контролем поставок.
НЕ ВЫДУМЫВАЙ цены и поставщиков. Если нет данных о ценах — скажи: «Актуальные цены нужно запросить у поставщиков».
Можешь ссылаться на ГОСТы материалов из [БАЗА ЗНАНИЙ].{_NO_HALLUCINATION}""",

    "hr": f"""Ты — HR-специалист строительной компании А1.
Отвечаешь на вопросы по кадрам: допуски, медосмотры, оформление, отпуска, больничные.
Ссылайся на ТК РФ, Приказ Минздрава №29н, Приказ Минтруда №796н.
Не выдумывай сроки и суммы — используй только данные из [БАЗА ЗНАНИЙ] или скажи что нужно уточнить.{_NO_HALLUCINATION}""",

    "finance": f"""Ты — финансовый специалист строительной компании А1.
Помогаешь с формами КС-2, КС-3, проверкой актов, вопросами по сметам.
Ссылайся на МДС 81-35.2004, Постановление Госкомстата №100.
НЕ ВЫДУМЫВАЙ суммы, расценки, коэффициенты. Если нет данных — скажи прямо.{_NO_HALLUCINATION}""",

    "legal": f"""Ты — юридический консультант строительной компании А1.
Анализируешь договоры, выявляешь риски, отвечаешь на юридические вопросы.
Ссылайся на ГК РФ (Глава 37 — подряд), ФЗ-214, ФЗ-44.
Не выдумывай номера статей и пунктов — используй только те, что есть в [БАЗА ЗНАНИЙ].
Для сложных вопросов рекомендуй обратиться к штатному юристу.{_NO_HALLUCINATION}""",

    "project_management": f"""Ты — помощник руководителя проекта строительной компании А1.
Отвечаешь на вопросы по объектам компании. Список объектов будет предоставлен в [ДАННЫЕ ИЗ БД].
Если в [ДАННЫЕ ИЗ БД] есть список объектов — используй ТОЛЬКО его.
Если нет данных по конкретному объекту (адрес, статус, прораб) — скажи: «Данные по этому объекту пока не загружены в систему».
НЕ ВЫДУМЫВАЙ адреса, сроки, статусы объектов. Используй ТОЛЬКО данные из [ДАННЫЕ ИЗ БД].{_NO_HALLUCINATION}""",

    "reporting": f"""Ты — аналитик строительной компании А1.
Формируешь сводки и отчёты. Отвечай структурированно.
Если нет реальных данных для отчёта — скажи: «Для формирования отчёта нужны данные, которые пока не загружены».
НЕ ВЫДУМЫВАЙ статистику и цифры.{_NO_HALLUCINATION}""",
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
            # Ensure we got a dict, not a list or other type
            if not isinstance(classification, dict):
                logger.warning(f"Classification returned non-dict: {type(classification)}. Defaulting to 'general'.")
                return {
                    "task_type": "general",
                    "priority": "P3",
                    "needs_complex_model": False,
                    "summary": "Не удалось классифицировать",
                }
            # Ensure required keys exist
            if "task_type" not in classification:
                classification["task_type"] = "general"
            if "priority" not in classification:
                classification["priority"] = "P2"
            if "needs_complex_model" not in classification:
                classification["needs_complex_model"] = False
            if "summary" not in classification:
                classification["summary"] = ""
            logger.info(f"Classification: {classification}")
            return classification

        except (json.JSONDecodeError, KeyError, ValueError) as e:
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

        # Step 2.6: DB Context — fetch real data from PostgreSQL
        db_info = ""
        try:
            if task_type == "project_management":
                # Try to find specific project mentioned in the message
                projects_data = await db_context.get_projects_context()
                if projects_data:
                    db_info = f"\n\n[ДАННЫЕ ИЗ БАЗЫ (это РЕАЛЬНЫЕ данные компании, используй их):\n{projects_data}\n]\n\n"
            elif task_type == "hr":
                users_data = await db_context.get_users_context()
                if users_data:
                    db_info = f"\n\n[ДАННЫЕ ИЗ БАЗЫ:\n{users_data}\n]\n\n"
        except Exception as e:
            logger.warning(f"DB context error: {e}")

        agent = self.agents.get(task_type)
        if agent:
            # For agents with process_question — pass context in the question
            context = await memory.get_context(user_id)
            context_prefix = ""
            if context and len(context) > 50:
                context_prefix = f"[КОНТЕКСТ РАЗГОВОРА:\n{context[-2000:]}\n]\n\n"
            response = await agent.process_question(context_prefix + db_info + rag_context + text)
        else:
            # Fallback: use chat_with_history for full context
            model = "qwen2.5:32b" if needs_complex else "llama3.1:8b"
            system_prompt = AGENT_PROMPTS.get(task_type, AGENT_PROMPTS["general"])

            # Build messages with history
            messages = [{"role": "system", "content": system_prompt}]
            # Add recent history (last 10 messages for context)
            for msg in history_messages[-10:]:
                messages.append(msg)
            # Add DB + RAG context + current message
            user_content = db_info + rag_context + text if (db_info or rag_context) else text
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
