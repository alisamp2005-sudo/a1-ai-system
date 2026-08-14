"""
Whisper Service — распознавание речи на хосте (Apple Silicon).
Работает как HTTP-сервис на порту 11436.
Модель скачивается один раз и кэшируется.

Запуск: python3 scripts/whisper_service.py
"""

import os
import io
import logging
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
logger = logging.getLogger("whisper_service")

app = FastAPI(title="A1 Whisper Service")

# Глобальная модель
whisper_model = None

MODEL_SIZE = os.getenv("WHISPER_MODEL", "large-v3")


@app.on_event("startup")
async def load_model():
    """Загрузка модели Whisper при старте сервиса."""
    global whisper_model
    logger.info(f"Загрузка модели Whisper {MODEL_SIZE}...")
    logger.info("Первый запуск может занять 1-3 минуты (скачивание модели)...")

    from faster_whisper import WhisperModel

    # На Apple Silicon используем CPU с int8 (Metal не поддерживается faster-whisper)
    whisper_model = WhisperModel(
        MODEL_SIZE,
        device="cpu",
        compute_type="int8",
    )
    logger.info("✅ Модель Whisper загружена успешно!")


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Принимает аудиофайл, возвращает распознанный текст.
    """
    global whisper_model

    if whisper_model is None:
        return JSONResponse(
            status_code=503,
            content={"error": "Модель ещё загружается, подождите..."},
        )

    try:
        # Сохраняем временный файл
        suffix = Path(file.filename).suffix if file.filename else ".ogg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # Распознаём
        segments, info = whisper_model.transcribe(
            tmp_path,
            language="ru",
            beam_size=5,
            vad_filter=True,
        )

        # Собираем текст
        text = " ".join([segment.text.strip() for segment in segments])

        # Удаляем временный файл
        os.unlink(tmp_path)

        logger.info(f"Распознано: {text[:100]}...")

        return {
            "text": text,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }

    except Exception as e:
        logger.error(f"Ошибка распознавания: {e}")
        # Cleanup
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass
        return JSONResponse(
            status_code=500,
            content={"error": f"Ошибка распознавания: {str(e)}"},
        )


@app.get("/health")
async def health():
    """Проверка состояния сервиса."""
    return {
        "status": "ok" if whisper_model else "loading",
        "model": MODEL_SIZE,
    }


if __name__ == "__main__":
    logger.info(f"Запуск Whisper Service на порту 11436 (модель: {MODEL_SIZE})")
    uvicorn.run(app, host="0.0.0.0", port=11436, log_level="info")
