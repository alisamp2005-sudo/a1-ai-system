"""
Vision Service — отдельный HTTP-сервис для анализа фото через mlx-vlm.
Запускается на хосте (Mac), порт 11435.
Бот из Docker обращается через host.docker.internal:11435.

Запуск:
    python3 scripts/vision_service.py
"""

import base64
import io
import logging
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("vision_service")

app = FastAPI(title="A1 Vision Service", version="1.0")

# Глобальные переменные для модели
model = None
processor = None
MODEL_NAME = "mlx-community/Llama-3.2-11B-Vision-Instruct-8bit"


class AnalyzeRequest(BaseModel):
    image_base64: str
    prompt: str = ""


class AnalyzeResponse(BaseModel):
    result: str
    success: bool


def load_model():
    """Загрузка модели при старте сервиса."""
    global model, processor
    logger.info(f"Загрузка модели {MODEL_NAME}...")
    from mlx_vlm import load
    model, processor = load(MODEL_NAME)
    logger.info("Модель загружена успешно!")


@app.on_event("startup")
async def startup():
    load_model()


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME, "loaded": model is not None}


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_image(request: AnalyzeRequest):
    """Анализ изображения на нарушения ТБ."""
    if model is None:
        raise HTTPException(status_code=503, detail="Модель не загружена")

    try:
        from mlx_vlm import generate
        from mlx_vlm.prompt_utils import apply_chat_template
        from PIL import Image

        # Декодируем base64 в изображение
        image_data = base64.b64decode(request.image_base64)
        image = Image.open(io.BytesIO(image_data))

        # Сохраняем во временный файл (mlx-vlm требует путь)
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            image.save(tmp, format="JPEG")
            tmp_path = tmp.name

        # Промпт для анализа безопасности (на английском — перевод делает safety agent)
        if request.prompt:
            user_prompt = request.prompt
        else:
            user_prompt = (
                "You are a construction site safety inspector. "
                "Analyze this photo and identify ALL safety violations. "
                "Check for:\n"
                "1. Workers without hard hats\n"
                "2. Workers without safety vests or PPE\n"
                "3. Missing guardrails or barriers near edges\n"
                "4. Missing safety harnesses when working at height\n"
                "5. Improper scaffolding\n"
                "6. Electrical hazards\n"
                "7. Housekeeping issues (debris, tripping hazards)\n\n"
                "For each violation found, state:\n"
                "- What: specific violation\n"
                "- Severity: HIGH / MEDIUM / LOW\n\n"
                "If no violations are found, say 'No safety violations detected.'\n"
                "If this is not a construction site photo, say so.\n"
                "Be specific and concise. Do NOT repeat yourself."
            )

        # Формируем сообщение для модели
        formatted_prompt = apply_chat_template(
            processor,
            config=model.config,
            prompt=user_prompt,
            images=[tmp_path],
        )

        # Генерация ответа
        output = generate(
            model,
            processor,
            formatted_prompt,
            images=[tmp_path],
            max_tokens=512,
            temperature=0.4,
            repetition_penalty=1.3,
            repetition_context_size=100,
        )

        # Удаляем временный файл
        Path(tmp_path).unlink(missing_ok=True)

        logger.info(f"Анализ завершён, длина ответа: {len(output)} символов")
        return AnalyzeResponse(result=output, success=True)

    except Exception as e:
        logger.error(f"Ошибка анализа: {e}", exc_info=True)
        return AnalyzeResponse(result=f"Ошибка: {str(e)}", success=False)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=11435, log_level="info")
