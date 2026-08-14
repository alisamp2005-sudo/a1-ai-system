"""
Агент: Безопасность (Vision — анализ фото с объектов)

Двухшаговый процесс:
1. mlx-vlm (Llama 3.2 Vision 11B) анализирует фото на АНГЛИЙСКОМ
2. Ollama (Llama 3.1 8B) переводит результат на РУССКИЙ

Vision-сервис: http://host.docker.internal:11435
"""

import logging
import base64
import httpx

from src.utils.config import settings

logger = logging.getLogger(__name__)

# URL vision-сервиса (mlx-vlm на хосте)
VISION_SERVICE_URL = "http://host.docker.internal:11435"

TRANSLATE_PROMPT = """Ты — профессиональный переводчик технической документации по охране труда.
Переведи следующий отчёт инспекции строительной площадки с английского на русский язык.
Это стандартный акт проверки соблюдения техники безопасности — переводи точно и полностью.

Правила перевода:
- HIGH = ВЫСОКАЯ
- MEDIUM = СРЕДНЯЯ
- LOW = НИЗКАЯ
- "No safety violations detected" = "Нарушений ТБ не обнаружено"
- hard hat = защитная каска
- safety vest = сигнальный жилет
- guardrail = ограждение
- harness = страховочный пояс
- scaffolding = строительные леса
- PPE = СИЗ (средства индивидуальной защиты)

Формат ответа:
УРОВЕНЬ ОПАСНОСТИ: [ВЫСОКИЙ/СРЕДНИЙ/НИЗКИЙ/НЕТ НАРУШЕНИЙ]

НАРУШЕНИЯ:
- [описание каждого нарушения]

РЕКОМЕНДАЦИИ:
- [что нужно исправить]

Отчёт инспекции:
{text}"""


class SafetyAgent:
    """Analyzes construction site photos: Vision (EN) -> Ollama translate (RU)."""

    def __init__(self):
        self.ollama_url = settings.OLLAMA_URL
        self.text_model = "llama3.1:8b"
        self.vision_url = VISION_SERVICE_URL

    async def analyze_photo(self, image_path: str) -> str:
        """Analyze a photo: Vision (English) -> Llama 8B (translate to Russian)."""
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

                # Шаг 1: Анализ фото на АНГЛИЙСКОМ через Vision
                resp = await client.post(
                    f"{self.vision_url}/analyze",
                    json={"image_base64": image_data, "prompt": ""},
                    timeout=300.0,
                )

                if resp.status_code != 200:
                    logger.error(f"Vision service error: {resp.status_code} {resp.text[:200]}")
                    return "⚠️ Ошибка Vision-сервиса. Попробуйте позже."

                data = resp.json()
                if not data.get("success"):
                    logger.error(f"Vision analysis failed: {data.get('result')}")
                    return "⚠️ Ошибка при анализе фото. Попробуйте позже."

                english_result = data.get("result", "")
                logger.info(f"Vision analysis (EN): {english_result[:150]}...")

                # Шаг 2: Перевод на русский через Ollama (Llama 8B)
                translate_resp = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.text_model,
                        "prompt": TRANSLATE_PROMPT.format(text=english_result),
                        "stream": False,
                    },
                    timeout=60.0,
                )

                if translate_resp.status_code == 200:
                    russian_result = translate_resp.json().get("response", "")
                else:
                    # Если перевод не удался — показываем английский
                    russian_result = english_result

            return self._format_response(russian_result, english_result)

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

    def _format_response(self, russian_text: str, english_text: str) -> str:
        """Format the final response with severity badge."""
        # Determine severity from English text (more reliable)
        severity = "🟡 СРЕДНЯЯ"
        eng_lower = english_text.lower()
        if any(w in eng_lower for w in ["high", "no hard hat", "no harness", "fall", "electr"]):
            severity = "🔴 ВЫСОКАЯ"
        elif "no safety violations" in eng_lower or "no violations" in eng_lower:
            severity = "🟢 НЕТ НАРУШЕНИЙ"
        elif any(w in eng_lower for w in ["low", "minor", "housekeeping"]):
            severity = "🟡 НИЗКАЯ"

        return (
            f"🦺 <b>АНАЛИЗ БЕЗОПАСНОСТИ</b>\n"
            f"⚠️ Степень: {severity}\n\n"
            f"{russian_text}\n\n"
            f"<i>Ответственный: Поляков С.Б.</i>"
        )
