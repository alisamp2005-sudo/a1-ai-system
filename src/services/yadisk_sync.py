"""
Yandex Disk Sync Service — синхронизация документов из публичной папки Яндекс.Диска.
Проверяет папку раз в день, скачивает новые файлы, загружает в RAG с привязкой к объекту.
"""

import logging
import os
import json
import hashlib
import tempfile
from datetime import datetime
from typing import Optional, List, Dict

import requests

from src.services.document_processor import extract_text, is_supported
from src.services.rag_service import rag_service

logger = logging.getLogger(__name__)

# Public Yandex Disk folder URL
YADISK_PUBLIC_URL = "https://disk.yandex.ru/d/-4W75tS2bYOqWw"
YADISK_API_BASE = "https://cloud-api.yandex.net/v1/disk/public/resources"

# Registry of synced files
SYNC_REGISTRY_PATH = "/app/data/yadisk_sync_registry.json"
DOCUMENT_REGISTRY_PATH = "/app/data/loaded_documents.json"


def _load_sync_registry() -> dict:
    """Load sync registry (tracks which files have been synced)."""
    try:
        if os.path.exists(SYNC_REGISTRY_PATH):
            with open(SYNC_REGISTRY_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"synced_files": {}, "last_sync": None}


def _save_sync_registry(registry: dict):
    """Save sync registry."""
    os.makedirs(os.path.dirname(SYNC_REGISTRY_PATH), exist_ok=True)
    with open(SYNC_REGISTRY_PATH, "w") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _register_document(filename: str, title: str, category: str, content_hash: str,
                       chunks: int, project_name: str, source: str = "yadisk"):
    """Register document in the main registry with project link."""
    os.makedirs(os.path.dirname(DOCUMENT_REGISTRY_PATH), exist_ok=True)
    try:
        if os.path.exists(DOCUMENT_REGISTRY_PATH):
            with open(DOCUMENT_REGISTRY_PATH, "r") as f:
                registry = json.load(f)
        else:
            registry = {"documents": []}
    except Exception:
        registry = {"documents": []}

    registry["documents"].append({
        "filename": filename,
        "title": title,
        "category": category,
        "content_hash": content_hash,
        "chunks": chunks,
        "project_name": project_name,
        "source": source,
        "loaded_at": datetime.now().isoformat(),
        "loaded_by": "Яндекс.Диск (авто)",
    })

    with open(DOCUMENT_REGISTRY_PATH, "w") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _get_file_hash(content: bytes) -> str:
    """Get SHA256 hash of file content."""
    return hashlib.sha256(content).hexdigest()[:16]


def _map_folder_to_project(folder_name: str) -> str:
    """Map Yandex Disk folder name to project name in DB."""
    # Direct mapping based on known folder names
    mapping = {
        '"Дом юстиции" г. Великий Новгород': 'Дом юстиции (Великий Новгород)',
        'АО "ГАЗСТРОЙПРОМ" Минск': 'АО "ГАЗСТРОЙПРОМ" Минск',
        'АО "ЩЛЗ" Лифты': 'АО "ЩЛЗ" Лифты',
        'АО "ЩЛЗ" Стройка': 'АО "ЩЛЗ" Стройка',
        'Алые паруса': 'Алые паруса',
        'ДРОЗ': 'ДРОЗ',
        'ЖК «ЛДМ» СПБ': 'ЖК «ЛДМ» СПБ',
        'Кубинка': 'Кубинка',
        'Ленская 15': 'Ленская 15',
        'Мосводосток Дмитровское шоссе': 'Мосводосток Дмитровское шоссе',
        'Остров-8': 'Остров-8',
        'ППК ВСК (Ульяновск.Поливно)': 'ППК ВСК (Ульяновск, Поливно)',
        'ППК ВСК (Чебаркуль)': 'ППК ВСК (Чебаркуль)',
        'Хранилища': 'Хранилища',
        'реновация': 'Реновация (Михалковская)',
        'ул.Житная. ФБУ РФЦСЭ при Минюсте России': 'ул. Житная (ФБУ РФЦСЭ при Минюсте)',
    }
    return mapping.get(folder_name, folder_name)


def _guess_category(filename: str) -> str:
    """Guess document category from filename."""
    fn_lower = filename.lower()
    if 'договор' in fn_lower or 'дог' in fn_lower or 'контракт' in fn_lower:
        return 'contract'
    elif 'акт' in fn_lower or 'кс-2' in fn_lower or 'кс-3' in fn_lower:
        return 'act'
    elif 'смет' in fn_lower or 'расчет' in fn_lower or 'кс-6' in fn_lower:
        return 'estimate'
    elif 'протокол' in fn_lower:
        return 'protocol'
    elif 'инструкц' in fn_lower or 'регламент' in fn_lower:
        return 'regulation'
    elif 'приказ' in fn_lower or 'заявлен' in fn_lower:
        return 'hr'
    elif 'тб' in fn_lower or 'безопасн' in fn_lower or 'охран' in fn_lower:
        return 'safety'
    elif 'заявк' in fn_lower or 'тмц' in fn_lower:
        return 'request'
    elif 'письм' in fn_lower or 'уведомл' in fn_lower:
        return 'letter'
    elif 'отчет' in fn_lower or 'отчёт' in fn_lower:
        return 'report'
    return 'other'


def list_public_folder(public_url: str, path: str = "/") -> List[Dict]:
    """List files in a public Yandex Disk folder."""
    try:
        params = {
            "public_key": public_url,
            "path": path,
            "limit": 100,
        }
        resp = requests.get(YADISK_API_BASE, params=params, timeout=30)
        if resp.status_code != 200:
            logger.warning(f"Yandex Disk API error: {resp.status_code}")
            return []

        data = resp.json()
        items = data.get("_embedded", {}).get("items", [])
        return items
    except Exception as e:
        logger.error(f"Error listing Yandex Disk folder: {e}")
        return []


def download_public_file(public_url: str, path: str) -> Optional[bytes]:
    """Download a file from public Yandex Disk folder."""
    try:
        # Get download link
        params = {
            "public_key": public_url,
            "path": path,
        }
        resp = requests.get(
            "https://cloud-api.yandex.net/v1/disk/public/resources/download",
            params=params,
            timeout=30
        )
        if resp.status_code != 200:
            logger.warning(f"Cannot get download link: {resp.status_code}")
            return None

        download_url = resp.json().get("href")
        if not download_url:
            return None

        # Download file
        file_resp = requests.get(download_url, timeout=120)
        if file_resp.status_code == 200:
            return file_resp.content
        return None
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        return None


async def sync_yadisk():
    """
    Main sync function — checks Yandex Disk for new/updated files.
    Called by Celery Beat once a day.
    """
    logger.info("Starting Yandex Disk sync...")
    sync_registry = _load_sync_registry()
    synced_files = sync_registry.get("synced_files", {})

    stats = {"new": 0, "skipped": 0, "errors": 0}

    # List top-level folders (each = one project)
    top_items = list_public_folder(YADISK_PUBLIC_URL)

    for item in top_items:
        item_name = item.get("name", "")
        item_type = item.get("type", "")
        item_path = item.get("path", "")

        if item_type == "dir":
            # This is a project folder — list its contents
            project_name = _map_folder_to_project(item_name)
            logger.info(f"Scanning folder: {item_name} → project: {project_name}")

            folder_path = item.get("path", f"/{item_name}")
            folder_items = list_public_folder(YADISK_PUBLIC_URL, path=folder_path)

            for file_item in folder_items:
                file_name = file_item.get("name", "")
                file_path = file_item.get("path", "")
                file_size = file_item.get("size", 0)
                file_modified = file_item.get("modified", "")

                # Check if supported format
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.csv', '.pptx']:
                    continue

                # Check if already synced (by path + modified date)
                sync_key = f"{item_name}/{file_name}"
                if sync_key in synced_files:
                    if synced_files[sync_key].get("modified") == file_modified:
                        stats["skipped"] += 1
                        continue

                # Download and process
                logger.info(f"  Downloading: {file_name} ({file_size} bytes)")
                file_dl_path = file_item.get("path", f"/{item_name}/{file_name}")
                content = download_public_file(YADISK_PUBLIC_URL, file_dl_path)

                if not content:
                    stats["errors"] += 1
                    continue

                # Check hash for duplicates
                file_hash = _get_file_hash(content)
                if any(d.get("content_hash") == file_hash for d in
                       _load_sync_registry().get("synced_files", {}).values()
                       if isinstance(d, dict)):
                    stats["skipped"] += 1
                    continue

                # Save to temp file and extract text
                try:
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name

                    text = await extract_text(tmp_path)
                    os.unlink(tmp_path)

                    # Handle tuple return from extract_text
                    if isinstance(text, tuple):
                        text = text[0] if text else ""
                    if not text:
                        text = ""

                    if not text or len(text.strip()) < 50:
                        logger.warning(f"  No text extracted from {file_name}")
                        stats["errors"] += 1
                        continue

                    # Load into RAG
                    category = _guess_category(file_name)
                    title = os.path.splitext(file_name)[0]

                    chunks_count = await rag_service.add_document(
                        text=text,
                        category=category,
                        title=title,
                        source=f"yadisk:{item_name}/{file_name}",
                        project_name=project_name,
                    )

                    # Register
                    _register_document(
                        filename=file_name,
                        title=title,
                        category=category,
                        content_hash=file_hash,
                        chunks=chunks_count,
                        project_name=project_name,
                        source="yadisk",
                    )

                    # Update sync registry
                    synced_files[sync_key] = {
                        "modified": file_modified,
                        "content_hash": file_hash,
                        "synced_at": datetime.now().isoformat(),
                    }

                    stats["new"] += 1
                    logger.info(f"  ✅ Loaded: {file_name} ({chunks_count} chunks)")

                except Exception as e:
                    logger.error(f"  Error processing {file_name}: {e}")
                    stats["errors"] += 1
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)

        elif item_type == "file":
            # Top-level file (e.g., Реестр контрактов)
            file_name = item_name
            ext = os.path.splitext(file_name)[1].lower()
            if ext not in ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.csv']:
                continue

            sync_key = file_name
            file_modified = item.get("modified", "")
            if sync_key in synced_files:
                if synced_files[sync_key].get("modified") == file_modified:
                    stats["skipped"] += 1
                    continue

            logger.info(f"Downloading top-level: {file_name}")
            file_dl_path = item.get("path", f"/{file_name}")
            content = download_public_file(YADISK_PUBLIC_URL, file_dl_path)

            if content:
                file_hash = _get_file_hash(content)
                try:
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                        tmp.write(content)
                        tmp_path = tmp.name

                    text = await extract_text(tmp_path)
                    os.unlink(tmp_path)

                    # Handle tuple return
                    if isinstance(text, tuple):
                        text = text[0] if text else ""
                    if not text:
                        text = ""

                    if text and len(text.strip()) >= 50:
                        category = _guess_category(file_name)
                        title = os.path.splitext(file_name)[0]

                        chunks_count = await rag_service.add_document(
                            text=text,
                            category=category,
                            title=title,
                            source=f"yadisk:{file_name}",
                            project_name="Общие документы",
                        )

                        _register_document(
                            filename=file_name,
                            title=title,
                            category=category,
                            content_hash=file_hash,
                            chunks=chunks_count,
                            project_name="Общие документы",
                            source="yadisk",
                        )

                        synced_files[sync_key] = {
                            "modified": file_modified,
                            "content_hash": file_hash,
                            "synced_at": datetime.now().isoformat(),
                        }
                        stats["new"] += 1
                except Exception as e:
                    logger.error(f"Error processing {file_name}: {e}")
                    stats["errors"] += 1

    # Save sync state
    sync_registry["synced_files"] = synced_files
    sync_registry["last_sync"] = datetime.now().isoformat()
    sync_registry["last_stats"] = stats
    _save_sync_registry(sync_registry)

    logger.info(f"Yandex Disk sync complete: {stats}")
    return stats
