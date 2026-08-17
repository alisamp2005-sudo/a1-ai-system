"""
RAG Service — поиск и загрузка документов в базу знаний ChromaDB.

Сервис используется ботом, админ-панелью и ежедневной синхронизацией
Яндекс.Диска. Все вызовы являются синхронными, поэтому вызывающие async-
обработчики не должны использовать ``await`` для методов этого класса.
"""

import hashlib
import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import chromadb
import requests

logger = logging.getLogger(__name__)

# В Docker сервисы общаются по внутреннему DNS-имени Compose. При локальном
# запуске можно задать CHROMA_URL=http://localhost:8000.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434")
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "a1_knowledge_base"
DEFAULT_CHUNK_SIZE = 200
DEFAULT_CHUNK_OVERLAP = 30

# Категории интерфейса загрузки отличаются от типов маршрутизации Router.
# Этот маппинг позволяет искать, например, договоры через агента lawyer.
CATEGORY_TO_AGENT = {
    "contract": "lawyer",
    "letter": "lawyer",
    "act": "finance",
    "estimate": "finance",
    "regulation": "secretary",
    "protocol": "secretary",
    "normative": "analyst",
    "request": "procurement",
    "safety": "safety",
    "hr": "hr",
    "report": "reporter",
    "other": "analyst",
}


class RAGService:
    """Сервис поиска и пополнения базы знаний А1."""

    def __init__(self) -> None:
        self._client: Any = None
        self._collection: Any = None

    @staticmethod
    def _connection_params() -> tuple[str, int, bool]:
        """Return host, port and SSL flag parsed from CHROMA_URL."""
        normalized_url = CHROMA_URL if "://" in CHROMA_URL else f"http://{CHROMA_URL}"
        parsed = urlparse(normalized_url)
        host = parsed.hostname or "chromadb"
        port = parsed.port or (443 if parsed.scheme == "https" else 8000)
        return host, port, parsed.scheme == "https"

    def _get_client(self) -> Any:
        """Create an HTTP client lazily and retain it for the process lifetime."""
        if self._client is None:
            host, port, ssl = self._connection_params()
            self._client = chromadb.HttpClient(host=host, port=port, ssl=ssl)
        return self._client

    def _get_collection(self, create: bool = False):
        """Connect to the knowledge-base collection, optionally creating it."""
        if self._collection is not None:
            return self._collection

        try:
            client = self._get_client()
            if create:
                self._collection = client.get_or_create_collection(
                    name=COLLECTION_NAME,
                    metadata={"description": "А1 Knowledge Base"},
                )
            else:
                self._collection = client.get_collection(COLLECTION_NAME)
            logger.info("RAG: подключен к коллекции '%s'", COLLECTION_NAME)
            return self._collection
        except Exception as exc:
            # The client itself can become stale after a Chroma restart.
            self._client = None
            self._collection = None
            logger.warning("RAG: не удалось подключиться к ChromaDB: %s", exc)
            return None

    def healthcheck(self) -> Dict[str, Any]:
        """Return a compact, non-throwing status for diagnostics."""
        collection = self._get_collection(create=False)
        if collection is None:
            return {"ok": False, "collection": COLLECTION_NAME, "count": 0}
        try:
            return {"ok": True, "collection": COLLECTION_NAME, "count": collection.count()}
        except Exception as exc:
            logger.warning("RAG: collection count error: %s", exc)
            return {"ok": False, "collection": COLLECTION_NAME, "count": 0}

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[str]:
        """Split text into overlapping chunks, safe for nomic-embed-text."""
        words = text.split()
        if not words:
            return []

        chunks: List[str] = []
        step = max(1, chunk_size - overlap)
        for start in range(0, len(words), step):
            chunk = " ".join(words[start:start + chunk_size]).strip()
            if len(chunk) >= 50:
                chunks.append(chunk)
        return chunks or [text[:6000].strip()]

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Generate an embedding locally through Ollama."""
        try:
            # 6000 characters is deliberately below nomic-embed-text context limits.
            response = requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text[:6000]},
                timeout=30,
            )
            if response.status_code == 200:
                embedding = response.json().get("embedding")
                return embedding if embedding else None
            logger.warning("RAG: embedding error %s: %s", response.status_code, response.text[:300])
        except Exception as exc:
            logger.warning("RAG: embedding request failed: %s", exc)
        return None

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        agent: Optional[str] = None,
        n_results: int = 3,
    ) -> str:
        """Find relevant fragments and return them as a context block for an agent."""
        collection = self._get_collection(create=False)
        if collection is None:
            return ""

        embedding = self._get_embedding(query)
        if embedding is None:
            return ""

        try:
            where_filter = {"category": category} if category else ({"agent": agent} if agent else None)
            results = collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where=where_filter,
            )
            documents = results.get("documents", [[]])[0]
            metadata_rows = results.get("metadatas", [[]])[0]
            if not documents:
                return ""

            fragments: List[str] = []
            for index, document in enumerate(documents):
                metadata = metadata_rows[index] if index < len(metadata_rows) else {}
                source = metadata.get("title") or metadata.get("source") or "Неизвестный источник"
                fragments.append(f"[{source}]\n{document}")
            return "\n\n---\n\n".join(fragments)
        except Exception as exc:
            logger.warning("RAG: search error: %s", exc)
            return ""

    def add_document(self, doc_id: str, text: str, metadata: Dict[str, Any]) -> bool:
        """Add or update one prepared RAG chunk. Used by Telegram ingestion."""
        collection = self._get_collection(create=True)
        if collection is None:
            return False

        embedding = self._get_embedding(text)
        if embedding is None:
            return False

        # Chroma metadata values must be scalar. Empty values are removed.
        safe_metadata = {
            str(key): value
            for key, value in metadata.items()
            if value is not None and isinstance(value, (str, int, float, bool))
        }
        try:
            collection.upsert(
                ids=[doc_id],
                documents=[text],
                embeddings=[embedding],
                metadatas=[safe_metadata],
            )
            return True
        except Exception as exc:
            logger.error("RAG: add_document error: %s", exc)
            return False

    def add_text_document(
        self,
        *,
        text: str,
        category: str,
        title: str,
        source: str,
        project_name: str = "",
        department: str = "",
        comment: str = "",
        agent: str = "",
    ) -> int:
        """Chunk and load an entire document. Returns number of saved chunks."""
        normalized_text = (text or "").strip()
        if not normalized_text:
            return 0

        document_key = hashlib.sha256(
            f"{source}|{title}|{normalized_text[:1000]}".encode("utf-8")
        ).hexdigest()[:20]
        agent = agent or CATEGORY_TO_AGENT.get(category, "analyst")
        chunks = self._chunk_text(normalized_text)
        saved = 0

        for index, chunk in enumerate(chunks):
            metadata: Dict[str, Any] = {
                "source": source,
                "title": title,
                "category": category or "other",
                "project_name": project_name,
                "department": department,
                "comment": comment,
                "agent": agent,
                "chunk_index": index,
                "document_key": document_key,
            }
            if self.add_document(
                doc_id=f"doc_{document_key}_{index}",
                text=chunk,
                metadata=metadata,
            ):
                saved += 1

        logger.info("RAG: загружен документ '%s': %s/%s фрагментов", title, saved, len(chunks))
        return saved


# Singleton instance
rag_service = RAGService()
