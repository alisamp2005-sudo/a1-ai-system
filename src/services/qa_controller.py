"""
QA Controller — validates agent responses before sending to the user.

Checks for:
1. Hallucinations (making up facts, citing non-existent laws)
2. Inappropriate content
3. Contradictions with company rules
4. Incomplete or too short answers
5. Language quality (Russian)
"""

import logging
from typing import Tuple

from src.services.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """Ты — контролер качества AI-системы строительной компании А1.
Твоя задача — проверить ответ AI-агента перед отправкой пользователю.

Проверь ответ по следующим критериям:
1. ГАЛЛЮЦИНАЦИИ: Не выдумывает ли агент факты, номера законов, даты, цифры?
2. АДЕКВАТНОСТЬ: Ответ по теме вопроса? Не уходит в сторону?
3. ПОЛНОТА: Ответ достаточно информативен? Не слишком ли короткий?
4. БЕЗОПАСНОСТЬ: Нет ли опасных рекомендаций (особенно по ТБ)?
5. ЯЗЫК: Ответ на русском, грамотный, профессиональный?

Ответь СТРОГО в формате JSON:
{"approved": true/false, "reason": "причина отклонения если false", "severity": "low/medium/high"}

Если ответ нормальный — {"approved": true, "reason": "", "severity": "low"}
Отклоняй ТОЛЬКО если есть явная проблема. Не придирайся к мелочам.
"""


class QAController:
    """Validates agent responses before delivery to user."""

    def __init__(self, ollama: OllamaClient):
        self.ollama = ollama
        self.enabled = True  # Can be disabled for testing

    async def validate_response(
        self,
        user_question: str,
        agent_response: str,
        task_type: str,
    ) -> Tuple[bool, str]:
        """
        Validate an agent's response.

        Args:
            user_question: Original user question
            agent_response: Agent's generated response
            task_type: Type of task (safety, legal, etc.)

        Returns:
            Tuple of (is_approved, reason_if_rejected)
        """
        if not self.enabled:
            return True, ""

        # Skip QA for very short responses (system messages, errors)
        if len(agent_response) < 30:
            return True, ""

        # For safety-critical responses, always check
        # For general questions, check only if response is long
        if task_type not in ("safety", "legal", "finance") and len(agent_response) < 200:
            return True, ""

        prompt = (
            f"ВОПРОС ПОЛЬЗОВАТЕЛЯ:\n{user_question}\n\n"
            f"ОТВЕТ АГЕНТА ({task_type}):\n{agent_response}\n\n"
            f"Проверь этот ответ по критериям качества."
        )

        try:
            import json

            result = await self.ollama.generate(
                prompt=prompt,
                model="llama3.1:8b",  # Use fast model for QA
                system_prompt=QA_SYSTEM_PROMPT,
                temperature=0.1,
            )

            # Parse JSON
            clean_result = result.strip()
            if clean_result.startswith("```"):
                clean_result = clean_result.split("\n", 1)[1]
                clean_result = clean_result.rsplit("```", 1)[0]

            qa_result = json.loads(clean_result)
            approved = qa_result.get("approved", True)
            reason = qa_result.get("reason", "")
            severity = qa_result.get("severity", "low")

            if not approved:
                logger.warning(
                    f"QA REJECTED [{severity}]: {reason} "
                    f"(type={task_type}, question={user_question[:50]})"
                )

                # For high severity, block the response
                if severity == "high":
                    return False, reason

                # For medium, add a disclaimer
                if severity == "medium":
                    return True, reason  # Approved but with warning

            return True, ""

        except Exception as e:
            # If QA fails, let the response through (fail-open)
            logger.error(f"QA Controller error: {e}. Passing response through.")
            return True, ""

    def get_disclaimer(self, reason: str) -> str:
        """Generate a disclaimer to append to the response."""
        return (
            f"\n\n<i>⚠️ Обратите внимание: {reason}. "
            f"Рекомендуем проверить информацию у специалиста.</i>"
        )
