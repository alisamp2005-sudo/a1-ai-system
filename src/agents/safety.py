"""
Агент: Безопасность (Vision — анализ фото с объектов)

Функции:
1. Анализ фото на нарушения ТБ (каски, СИЗ, ограждения)
2. Классификация нарушений по степени опасности
3. Уведомление ответственного за ТБ (Поляков С.Б.)
4. Формирование отчета о нарушениях
"""

import logging
import base64
import httpx
from typing import Optional, Tuple

from src.utils.config import settings

logger = logging.getLogger(__name__)

SAFETY_SYSTEM_PROMPT = """You are an AI safety inspector for a construction site.

Analyze the photo and determine:
1. Are there any safety violations?
2. Type of violation (missing hard hat, missing PPE, no guardrails, no harness, etc.)
3. Severity: HIGH / MEDIUM / LOW
4. Recommendations to fix

Rules:
- If there are no people or no construction site in the photo, say so
- If unsure, say "on-site inspection required"
- Be specific: "worker without hard hat near edge of slab" is better than "safety violation"
- Respond in Russian language
"""


class SafetyAgent:
    """Analyzes photos from construction sites for safety violations using LLaVA."""

    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.model = "llama3.2-vision:11b"
        self.enabled = False

    async def check_model_available(self) -> bool:
        """Check if vision model is available in Ollama."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                if resp.status_code == 200:
                    models = resp.json().get("models", [])
                    for m in models:
                        if "llama3.2-vision" in m.get("name", "").lower() or "llava" in m.get("name", "").lower():
                            self.model = m.get("name", self.model)
                            self.enabled = True
                            return True
            return False
        except Exception:
            return False

    async def analyze_photo(self, image_path: str) -> str:
        """
        Analyze a photo for safety violations.

        Args:
            image_path: Path to the image file

        Returns:
            Analysis result text
        """
        if not self.enabled:
            available = await self.check_model_available()
            if not available:
                return (
                    "🦺 <b>Агент безопасности</b>\n\n"
                    "⚠️ Vision-модель не загружена. "
                    "Для анализа фото выполните на сервере:\n"
                    "<code>ollama pull llama3.2-vision:11b</code>"
                )

        try:
            # Read and encode image
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            # Send to Ollama with LLaVA
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": SAFETY_SYSTEM_PROMPT + "\n\nОпиши что видишь на фото и укажи нарушения ТБ.",
                        "images": [image_data],
                        "stream": False,
                    },
                )

                if resp.status_code == 200:
                    result = resp.json().get("response", "")
                    return self._format_response(result)
                else:
                    logger.error(f"LLaVA error: {resp.status_code} {resp.text}")
                    return "⚠️ Ошибка при анализе фото. Попробуйте позже."

        except Exception as e:
            logger.error(f"Safety analysis error: {e}")
            return "⚠️ Ошибка при анализе фото. Попробуйте позже."

    async def process_question(self, question: str) -> str:
        """Process a text safety question (without photo)."""
        from src.services.ollama_client import OllamaClient
        ollama = OllamaClient()
        response = await ollama.generate(
            prompt=question,
            model="llama3.1:8b",
            system_prompt=SAFETY_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return f"🦺 <b>Безопасность</b>\n\n{response}"

    def _format_response(self, raw_response: str) -> str:
        """Format the LLaVA response."""
        # Determine severity
        severity = "🟡 СРЕДНЯЯ"
        if any(word in raw_response.lower() for word in ["высокая", "опасно", "критич", "без каски", "без страховки"]):
            severity = "🔴 ВЫСОКАЯ"
        elif any(word in raw_response.lower() for word in ["нет нарушений", "всё в порядке", "соблюдены"]):
            severity = "🟢 НЕТ НАРУШЕНИЙ"

        return (
            f"🦺 <b>АНАЛИЗ БЕЗОПАСНОСТИ</b>\n"
            f"⚠️ Степень: {severity}\n\n"
            f"{raw_response}\n\n"
            f"<i>Ответственный: Поляков С.Б.</i>"
        )
