"""
Ollama API Client.
Communicates with the local Ollama server to run LLM inference.
"""

import logging
from typing import Optional

import httpx

from src.utils.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Client for Ollama API (OpenAI-compatible)."""

    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.timeout = 120.0  # LLM can take time to respond

    async def generate(
        self,
        prompt: str,
        model: str = "llama3.1:8b",
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
    ) -> str:
        """
        Generate a response from Ollama.

        Args:
            prompt: User message
            model: Model name (llama3.1:8b for simple, qwen2.5:32b for complex)
            system_prompt: System instruction for the model
            temperature: Creativity (0.0 = deterministic, 1.0 = creative)

        Returns:
            Generated text response
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]

        except httpx.TimeoutException:
            logger.error(f"Ollama timeout (model={model})")
            return "⚠️ Модель не ответила вовремя. Попробуйте позже."
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            return "⚠️ Ошибка подключения к AI-модели."
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "⚠️ Не удалось получить ответ от AI-модели."

    async def chat_with_history(
        self,
        messages: list,
        model: str = "llama3.1:8b",
        temperature: float = 0.3,
    ) -> str:
        """
        Generate a response with full message history.

        Args:
            messages: List of {"role": "system"/"user"/"assistant", "content": "..."}
            model: Model name
            temperature: Creativity

        Returns:
            Generated text response
        """
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["message"]["content"]

        except httpx.TimeoutException:
            logger.error(f"Ollama timeout (model={model})")
            return "⚠️ Модель не ответила вовремя. Попробуйте позже."
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code}")
            return "⚠️ Ошибка подключения к AI-модели."
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return "⚠️ Не удалось получить ответ от AI-модели."

    async def health_check(self) -> bool:
        """Check if Ollama is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
