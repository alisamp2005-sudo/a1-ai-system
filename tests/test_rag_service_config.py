"""Regression checks for RAG configuration that do not require running Docker."""

import os
import sys
import types

# This test only covers pure configuration; it does not start ChromaDB.
# A small module stub makes it runnable before optional dependencies are installed.
sys.modules.setdefault("chromadb", types.SimpleNamespace(HttpClient=lambda **_: None))

# Set the environment before importing module-level configuration.
os.environ["CHROMA_URL"] = "http://chromadb:8000"

from src.services.rag_service import CATEGORY_TO_AGENT, RAGService


def run() -> None:
    host, port, ssl = RAGService._connection_params()
    assert (host, port, ssl) == ("chromadb", 8000, False)
    assert CATEGORY_TO_AGENT["contract"] == "lawyer"
    assert CATEGORY_TO_AGENT["safety"] == "safety"
    assert CATEGORY_TO_AGENT["estimate"] == "finance"
    print("RAG configuration checks passed")


if __name__ == "__main__":
    run()
