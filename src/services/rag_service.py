"""
RAG Service — поиск по базе знаний (ChromaDB).

Агенты используют этот сервис для поиска релевантной информации
из нормативных документов перед формированием ответа.
"""

import os
import logging
from typing import List, Optional

import requests
import chromadb

logger = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
CHROMA_URL = os.getenv("CHROMA_URL", "http://host.docker.internal:8000")
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "a1_knowledge_base"


class RAGService:
    """Сервис поиска по базе знаний."""

    def __init__(self):
        self._client = None
        self._collection = None

    def _get_collection(self):
        """Lazy init ChromaDB connection."""
        if self._collection is None:
            try:
                # Parse host and port from CHROMA_URL
                url = CHROMA_URL.replace("http://", "").replace("https://", "")
                host, port = url.split(":")
                self._client = chromadb.HttpClient(host=host, port=int(port))
                self._collection = self._client.get_collection(COLLECTION_NAME)
                logger.info(f"RAG: подключен к коллекции '{COLLECTION_NAME}'")
            except Exception as e:
                logger.warning(f"RAG: не удалось подключиться к ChromaDB: {e}")
                return None
        return self._collection

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding from Ollama."""
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json()["embedding"]
            else:
                logger.warning(f"RAG: embedding error: {resp.status_code}")
                return None
        except Exception as e:
            logger.warning(f"RAG: embedding request failed: {e}")
            return None

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        agent: Optional[str] = None,
        n_results: int = 3,
    ) -> str:
        """
        Поиск релевантных фрагментов в базе знаний.

        Args:
            query: текст запроса пользователя
            category: фильтр по категории (safety, legal, finance, hr, procurement, project_management)
            agent: фильтр по агенту (safety, lawyer, finance, hr, procurement, secretary)
            n_results: количество результатов

        Returns:
            Строка с найденными фрагментами или пустая строка если ничего не найдено.
        """
        collection = self._get_collection()
        if collection is None:
            return ""

        embedding = self._get_embedding(query)
        if embedding is None:
            return ""

        try:
            # Build where filter
            where_filter = None
            if category:
                where_filter = {"category": category}
            elif agent:
                where_filter = {"agent": agent}

            results = collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=where_filter if where_filter else None,
            )

            if not results["documents"] or not results["documents"][0]:
                return ""

            # Format results
            fragments = []
            for i, doc in enumerate(results["documents"][0]):
                source = results["metadatas"][0][i].get("source", "Неизвестный источник")
                fragments.append(f"[{source}]\n{doc}")

            context = "\n\n---\n\n".join(fragments)
            return context

        except Exception as e:
            logger.warning(f"RAG: search error: {e}")
            return ""


# Singleton instance
rag_service = RAGService()
