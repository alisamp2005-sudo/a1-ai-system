"""
Whisper Speech-to-Text Service.
Calls the host Whisper service (port 11436) for transcription.
Model runs on Mac host (not inside Docker) for better performance and caching.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

WHISPER_URL = os.getenv("WHISPER_URL", "http://host.docker.internal:11436")


async def transcribe_voice(audio_path: str) -> Optional[str]:
    """
    Transcribe an audio file to text via the host Whisper service.

    Args:
        audio_path: Path to the audio file (OGG/MP3/WAV)

    Returns:
        Transcribed text or None if failed
    """
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/ogg")}
                response = await client.post(
                    f"{WHISPER_URL}/transcribe",
                    files=files,
                )

            if response.status_code == 200:
                data = response.json()
                text = data.get("text", "")
                duration = data.get("duration", 0)
                logger.info(f"Transcribed {duration:.1f}s audio -> {len(text)} chars")
                return text
            elif response.status_code == 503:
                logger.warning("Whisper service is still loading model...")
                return None
            else:
                logger.error(f"Whisper service error: {response.status_code} {response.text}")
                return None

    except httpx.ConnectError:
        logger.error(
            "Cannot connect to Whisper service. "
            "Make sure whisper_service.py is running on the host: "
            "python3 scripts/whisper_service.py"
        )
        return None
    except Exception as e:
        logger.error(f"Whisper transcription error: {e}")
        return None
