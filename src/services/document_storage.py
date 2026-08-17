"""Persistent originals and delivery controls for knowledge-base documents.

The RAG index stores extracted text only. This module keeps a local original copy
for files that are permitted to be returned to an authorized Telegram user.
"""

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

REGISTRY_PATH = Path("/app/data/loaded_documents.json")
STORAGE_DIR = Path("/app/data/documents")
AUTHORIZED_DOCUMENT_ROLES = {"admin", "top_manager"}


def sanitize_filename(filename: str) -> str:
    """Return a filesystem-safe filename while preserving its readable extension."""
    base_name = Path(filename or "document").name
    safe_name = re.sub(r"[^0-9A-Za-zА-Яа-яЁё._() -]+", "_", base_name).strip(" .")
    return safe_name[:180] or "document"


def content_hash(content: bytes) -> str:
    """Return a stable compact identifier for duplicate checks and callbacks."""
    return hashlib.sha256(content).hexdigest()[:16]


def save_original(content: bytes, filename: str, file_hash: Optional[str] = None) -> str:
    """Save an original file atomically and return its in-container absolute path."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    file_hash = file_hash or content_hash(content)
    path = STORAGE_DIR / f"{file_hash}_{sanitize_filename(filename)}"
    temporary_path = path.with_suffix(path.suffix + ".part")
    temporary_path.write_bytes(content)
    temporary_path.replace(path)
    return str(path)


def load_registry() -> Dict[str, List[Dict[str, Any]]]:
    """Load the shared document registry without raising on an absent/invalid file."""
    try:
        loaded = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict) and isinstance(loaded.get("documents"), list):
            return loaded
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {"documents": []}


def save_registry(registry: Dict[str, List[Dict[str, Any]]]) -> None:
    """Persist document metadata atomically."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = REGISTRY_PATH.with_suffix(".json.part")
    temporary_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_path.replace(REGISTRY_PATH)


def find_document(document_id: str) -> Optional[Dict[str, Any]]:
    """Return an available document registry entry by its compact identifier."""
    for document in load_registry().get("documents", []):
        if document.get("document_id") == document_id:
            storage_path = document.get("storage_path", "")
            if storage_path and Path(storage_path).is_file():
                return document
    return None


def build_delivery_keyboard(response_text: str, max_documents: int = 3) -> Optional[InlineKeyboardMarkup]:
    """Create Telegram-only download buttons for originals mentioned in an answer.

    Links are intentionally not exposed as public HTTP URLs: the callback lets the
    bot verify the actual Telegram account role before sending the original file.
    """
    text = (response_text or "").casefold()
    buttons: List[List[InlineKeyboardButton]] = []
    used_ids = set()

    for document in load_registry().get("documents", []):
        document_id = document.get("document_id", "")
        storage_path = document.get("storage_path", "")
        title = str(document.get("title") or "")
        filename = str(document.get("filename") or "")
        if not document_id or not storage_path or not Path(storage_path).is_file():
            continue

        candidates = [
            title.casefold(),
            title.split("(", 1)[0].strip().casefold(),
            Path(filename).stem.casefold(),
        ]
        if not any(candidate and len(candidate) >= 5 and candidate in text for candidate in candidates):
            continue
        if document_id in used_ids:
            continue

        visible_name = title or filename or "документ"
        if len(visible_name) > 38:
            visible_name = visible_name[:35].rstrip() + "…"
        buttons.append([
            InlineKeyboardButton(
                text=f"📎 Скачать: {visible_name}",
                callback_data=f"docget:{document_id}",
            )
        ])
        used_ids.add(document_id)
        if len(buttons) >= max_documents:
            break

    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def merge_keyboards(
    first: Optional[InlineKeyboardMarkup],
    second: Optional[InlineKeyboardMarkup],
) -> Optional[InlineKeyboardMarkup]:
    """Combine optional entity and document keyboards, preserving existing rows."""
    rows: List[List[InlineKeyboardButton]] = []
    if first:
        rows.extend(first.inline_keyboard)
    if second:
        rows.extend(second.inline_keyboard)
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
