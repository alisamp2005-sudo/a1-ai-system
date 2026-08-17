"""Dependency-light regression checks for secure original-document storage."""

import sys
import tempfile
import types
from pathlib import Path


class FakeButton:
    def __init__(self, text, callback_data=None, **kwargs):
        self.text = text
        self.callback_data = callback_data


class FakeMarkup:
    def __init__(self, inline_keyboard):
        self.inline_keyboard = inline_keyboard


sys.modules.setdefault(
    "aiogram.types",
    types.SimpleNamespace(InlineKeyboardButton=FakeButton, InlineKeyboardMarkup=FakeMarkup),
)

from src.services import document_storage


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        document_storage.REGISTRY_PATH = root / "loaded_documents.json"
        document_storage.STORAGE_DIR = root / "documents"

        payload = b"example contract body"
        identifier = document_storage.content_hash(payload)
        original_path = document_storage.save_original(payload, "Договор Остров-8.pdf", identifier)
        assert Path(original_path).read_bytes() == payload

        registry = {"documents": [{
            "document_id": identifier,
            "filename": "Договор Остров-8.pdf",
            "title": "Договор генподряда Остров-8",
            "storage_path": original_path,
        }]}
        document_storage.save_registry(registry)

        assert document_storage.find_document(identifier)["filename"] == "Договор Остров-8.pdf"
        keyboard = document_storage.build_delivery_keyboard("Покажи договор генподряда Остров-8")
        assert keyboard is not None
        assert keyboard.inline_keyboard[0][0].callback_data == f"docget:{identifier}"

    print("Document storage checks passed")


if __name__ == "__main__":
    run()
