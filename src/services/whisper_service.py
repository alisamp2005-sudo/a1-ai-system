"""
Whisper Speech-to-Text Service.
Uses faster-whisper for local transcription of voice messages.
"""

import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

# Lazy-load the model (heavy, ~3 GB)
_model = None


def get_whisper_model():
    """Lazy-load Whisper model on first use."""
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper Large v3 model... (first time, may take 30-60 seconds)")
        _model = WhisperModel(
            "large-v3",
            device="cpu",  # On Mac, CPU with Apple Silicon is fast enough
            compute_type="int8",  # Quantized for speed
        )
        logger.info("Whisper model loaded successfully!")
    return _model


async def transcribe_voice(audio_path: str) -> Optional[str]:
    """
    Transcribe an audio file to text using Whisper.

    Args:
        audio_path: Path to the audio file (OGG/MP3/WAV)

    Returns:
        Transcribed text or None if failed
    """
    try:
        import asyncio

        # Run transcription in a thread pool (it's CPU-bound)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _transcribe_sync, audio_path)
        return result

    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return None


def _transcribe_sync(audio_path: str) -> str:
    """Synchronous transcription (runs in thread pool)."""
    model = get_whisper_model()

    segments, info = model.transcribe(
        audio_path,
        language="ru",
        beam_size=5,
        vad_filter=True,  # Filter out silence
    )

    # Collect all segments
    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    full_text = " ".join(text_parts)
    logger.info(f"Transcribed {info.duration:.1f}s audio -> {len(full_text)} chars")
    return full_text
