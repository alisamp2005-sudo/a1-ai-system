"""
Агент: Безопасность (Vision — анализ фото с объектов)

Использует mlx-vlm (Llama 3.2 Vision 11B) через отдельный сервис на порту 11435.
Сервис запускается на хосте: python3 scripts/vision_service.py
"""

import logging
import base64
import httpx

from src.utils.config import settings

logger = logging.getLogger(__name__)

# URL vision-сервиса (mlx-vlm на хосте)
VISION_SERVICE_URL = "http://host.docker.internal:11435"


class SafetyAgent:
    """Analyzes construction site photos for safety violations via mlx-vlm."""

    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.text_model = "llama3.1:8b"
        self.vision_url = VISION_SERVICE_URL

    async def analyze_photo(self, image_path: str) -> str:
        """Analyze a photo via vision service (mlx-vlm on host)."""
        try:
            # Читаем фото и кодируем в base64
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            async with httpx.AsyncClient(timeout=300.0) as client:
                # Проверяем доступность vision-сервиса
                try:
                    health = await client.get(f"{self.vision_url}/health", timeout=5.0)
                    if health.status_code != 200:
                        return self._service_unavailable()
                except Exception:
                    return self._service_unavailable()

                # Отправляем фото на анализ
                resp = await client.post(
                    f"{self.vision_url}/analyze",
                    json={
                        "image_base64": image_data,
                        "prompt": "",  # Используем дефолтный промпт сервиса
                    },
                    timeout=300.0,
                )

                if resp.status_code != 200:
                    logger.error(f"Vision service error: {resp.status_code} {resp.text[:200]}")
                    return "⚠️ Ошибка Vision-сервиса. Попробуйте позже."

                data = resp.json()
                if not data.get("success"):
                    logger.error(f"Vision analysis failed: {data.get('result')}")
                    return "⚠️ Ошибка при анализе фото. Попробуйте позже."

                result_text = data.get("result", "")
                logger.info(f"Vision analysis done: {result_text[:100]}...")

            return self._format_response(result_text)

        except httpx.TimeoutException:
            logger.error("Safety analysis timeout (300s)")
            return (
                "🦺 <b>Агент безопасности</b>\n\n"
                "⏱ Анализ занял слишком много времени. "
                "Попробуйте отправить фото меньшего размера."
            )
        except Exception as e:
            logger.error(f"Safety analysis error: {e}")
            return "⚠️ Ошибка при анализе фото. Попробуйте позже."

    async def process_question(self, question: str) -> str:
        """Process a text safety question (without photo)."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.text_model,
                        "prompt": question,
                        "system": (
                            "Ты — специалист по технике безопасности на строительных "
                            "объектах в России. Отвечай кратко и по делу на русском языке. "
                            "Ссылайся на СНиП, СП и другие нормативные документы где уместно."
                        ),
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    result = resp.json().get("response", "")
                    return f"🦺 <b>Безопасность</b>\n\n{result}"
                return "⚠️ Ошибка при обработке вопроса."
        except Exception as e:
            logger.error(f"Safety question error: {e}")
            return "⚠️ Ошибка при обработке вопроса."

    def _service_unavailable(self) -> str:
        """Сообщение когда vision-сервис недоступен."""
        return (
            "🦺 <b>Агент безопасности</b>\n\n"
            "⚠️ Vision-сервис недоступен. Запустите на маке:\n"
            "<code>cd ~/a1-ai-system && python3 scripts/vision_service.py</code>"
        )

    def _format_response(self, text: str) -> str:
        """Format the final response with severity badge."""
        text_lower = text.lower()

        # Определяем уровень опасности
        if "высокий" in text_lower or "высокая" in text_lower:
            severity = "🔴 ВЫСОКАЯ"
        elif "нет нарушений" in text_lower or "не обнаружено" in text_lower:
            severity = "🟢 НЕТ НАРУШЕНИЙ"
        elif "низк" in text_lower:
            severity = "🟡 НИЗКАЯ"
        else:
            severity = "🟡 СРЕДНЯЯ"

        return (
            f"🦺 <b>АНАЛИЗ БЕЗОПАСНОСТИ</b>\n"
            f"⚠️ Степень: {severity}\n\n"
            f"{text}\n\n"
            f"<i>Ответственный: Поляков С.Б.</i>"
        )
