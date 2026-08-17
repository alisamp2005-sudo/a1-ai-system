"""
Document Upload Handlers — обработка файлов для загрузки в RAG.

Поток:
1. Пользователь отправляет файл (с подписью или без)
2. Бот извлекает текст
3. AI классифицирует документ
4. Бот показывает кнопки: [Сохранить] [Переименовать] [Отмена]
5. При подтверждении — загружает в ChromaDB
"""

import logging
import os
import json
import hashlib
import tempfile
from datetime import datetime
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.services.document_processor import (
    extract_text, is_supported, get_format_description, SUPPORTED_FORMATS
)
from src.services.ollama_client import OllamaClient
from src.services.rag_service import rag_service

# ============================================================
# DOCUMENT REGISTRY — tracks what's been loaded to prevent duplicates
# ============================================================
DOCUMENT_REGISTRY_PATH = "/app/data/loaded_documents.json"


def _load_registry() -> dict:
    """Load the document registry from disk."""
    try:
        if os.path.exists(DOCUMENT_REGISTRY_PATH):
            with open(DOCUMENT_REGISTRY_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"documents": []}


def _save_registry(registry: dict):
    """Save the document registry to disk."""
    os.makedirs(os.path.dirname(DOCUMENT_REGISTRY_PATH), exist_ok=True)
    with open(DOCUMENT_REGISTRY_PATH, "w") as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)


def _get_content_hash(text: str) -> str:
    """Get SHA256 hash of document content."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _check_duplicate(filename: str, content_hash: str) -> Optional[dict]:
    """Check if document is already loaded. Returns existing entry or None."""
    registry = _load_registry()
    for doc in registry["documents"]:
        if doc.get("content_hash") == content_hash:
            return doc
        if doc.get("filename") == filename:
            return doc
    return None


def _register_document(filename: str, title: str, category: str, content_hash: str, chunks: int, user: str):
    """Register a loaded document."""
    registry = _load_registry()
    registry["documents"].append({
        "filename": filename,
        "title": title,
        "category": category,
        "content_hash": content_hash,
        "chunks": chunks,
        "loaded_at": datetime.now().isoformat(),
        "loaded_by": user,
    })
    _save_registry(registry)

logger = logging.getLogger(__name__)

document_router = Router()

# Категории документов
DOCUMENT_CATEGORIES = {
    "contract": "📄 Договор",
    "act": "📋 Акт (КС-2, КС-3)",
    "regulation": "📖 Регламент/Инструкция",
    "normative": "📐 Норматив (СНиП, ГОСТ, СП)",
    "request": "📦 Заявка ТМЦ",
    "protocol": "📝 Протокол совещания",
    "report": "📊 Отчёт",
    "letter": "✉️ Письмо/Уведомление",
    "estimate": "💰 Смета/Расчёт",
    "safety": "🦺 Документ по ТБ",
    "hr": "👤 Кадровый документ",
    "other": "📁 Прочее",
}

CLASSIFY_PROMPT = """Ты — классификатор документов строительной компании А1.
Определи категорию документа по его содержимому.

Категории:
- contract: Договор (подряда, поставки, аренды и т.д.)
- act: Акт выполненных работ (КС-2, КС-3, акт приёмки)
- regulation: Регламент, инструкция, положение компании
- normative: Нормативный документ (СНиП, ГОСТ, СП, Приказ Минтруда)
- request: Заявка на ТМЦ, материалы, оборудование
- protocol: Протокол совещания, планёрки
- report: Отчёт (ежедневный, еженедельный, по объекту)
- letter: Письмо, уведомление, претензия
- estimate: Смета, расчёт стоимости, КС-6а
- safety: Документ по технике безопасности, инструкция по ОТ
- hr: Кадровый документ (приказ, заявление, трудовой договор)
- other: Не подходит ни к одной категории

Ответь СТРОГО в формате JSON:
{"category": "contract", "title": "Краткое название документа", "description": "Описание в 1 предложение"}

ТЕКСТ ДОКУМЕНТА (первые 2000 символов):
{text}
"""


class DocumentUploadStates(StatesGroup):
    """FSM states for document upload flow."""
    waiting_confirmation = State()
    waiting_rename = State()


@document_router.message(F.document)
async def handle_document(message: Message, state: FSMContext):
    """Handle incoming document files."""
    doc = message.document

    # Check if format is supported
    filename = doc.file_name or "unknown"
    if not is_supported(filename):
        ext = os.path.splitext(filename)[1].lower()
        supported_list = ", ".join(sorted(SUPPORTED_FORMATS.keys()))
        await message.answer(
            f"❌ Формат <b>{ext}</b> не поддерживается.\n\n"
            f"Поддерживаемые форматы:\n<code>{supported_list}</code>",
            parse_mode="HTML",
        )
        return

    # Show processing message
    format_desc = get_format_description(filename)
    status_msg = await message.answer(
        f"📄 Получен файл: <b>{filename}</b>\n"
        f"Тип: {format_desc}\n\n"
        f"⏳ Извлекаю текст...",
        parse_mode="HTML",
    )

    # Download file
    try:
        bot = message.bot
        file = await bot.get_file(doc.file_id)
        
        # Create temp file
        suffix = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            await bot.download_file(file.file_path, tmp)
            tmp_path = tmp.name

        # Extract text
        text, fmt = await extract_text(tmp_path)

        # Clean up temp file
        os.unlink(tmp_path)

        if not text or len(text.strip()) < 20:
            await status_msg.edit_text(
                f"📄 Файл: <b>{filename}</b>\n\n"
                f"⚠️ Не удалось извлечь текст из файла. "
                f"Возможно файл пустой, защищён паролем или содержит только изображения.",
                parse_mode="HTML",
            )
            return

        # Classify document with AI
        await status_msg.edit_text(
            f"📄 Файл: <b>{filename}</b>\n"
            f"✅ Текст извлечён ({len(text)} символов)\n\n"
            f"🤖 Классифицирую документ...",
            parse_mode="HTML",
        )

        # Use caption as hint if provided
        caption = message.caption or ""
        classification = await _classify_document(text, caption)

        category = classification.get("category", "other")
        title = classification.get("title", filename)
        description = classification.get("description", "")

        category_emoji = DOCUMENT_CATEGORIES.get(category, "📁 Прочее")

        # Store data in FSM for confirmation
        await state.set_state(DocumentUploadStates.waiting_confirmation)
        await state.update_data(
            text=text[:50000],  # Limit stored text
            filename=filename,
            category=category,
            title=title,
            description=description,
            user_caption=caption,
        )

        # Show classification and ask for confirmation
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data=f"doc_save"),
                InlineKeyboardButton(text="✏️ Переименовать", callback_data=f"doc_rename"),
            ],
            [
                InlineKeyboardButton(text="🔄 Другая категория", callback_data=f"doc_recat"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"doc_cancel"),
            ],
        ])

        await status_msg.edit_text(
            f"📄 <b>Документ распознан:</b>\n\n"
            f"📁 Категория: {category_emoji}\n"
            f"📌 Название: <b>{title}</b>\n"
            f"📝 Описание: {description}\n"
            f"📏 Размер текста: {len(text)} символов\n\n"
            f"Сохранить в базу знаний?",
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        logger.error(f"Document processing error: {e}")
        await status_msg.edit_text(
            f"❌ Ошибка при обработке файла: {str(e)[:200]}",
        )


@document_router.callback_query(F.data == "doc_save")
async def handle_doc_save(callback: CallbackQuery, state: FSMContext):
    """Save document to RAG."""
    data = await state.get_data()
    if not data.get("text"):
        await callback.answer("Данные документа не найдены. Отправьте файл заново.")
        await state.clear()
        return

    text = data["text"]
    category = data["category"]
    title = data["title"]
    filename = data["filename"]

    await callback.answer("Сохраняю...")
    await callback.message.edit_text(
        f"⏳ Загружаю в базу знаний...\n"
        f"📌 {title}",
    )

    # Check for duplicates
    content_hash = _get_content_hash(text)
    existing = _check_duplicate(filename, content_hash)
    if existing:
        await callback.message.edit_text(
            f"\u26a0\ufe0f <b>\u0414\u0443\u0431\u043b\u0438\u043a\u0430\u0442!</b>\n\n"
            f"\u042d\u0442\u043e\u0442 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0443\u0436\u0435 \u0437\u0430\u0433\u0440\u0443\u0436\u0435\u043d \u0432 \u0431\u0430\u0437\u0443 \u0437\u043d\u0430\u043d\u0438\u0439:\n"
            f"\ud83d\udccc {existing.get('title', filename)}\n"
            f"\ud83d\udcc5 \u0417\u0430\u0433\u0440\u0443\u0436\u0435\u043d: {existing.get('loaded_at', '?')[:10]}\n\n"
            f"\u041f\u043e\u0432\u0442\u043e\u0440\u043d\u0430\u044f \u0437\u0430\u0433\u0440\u0443\u0437\u043a\u0430 \u043d\u0435 \u0442\u0440\u0435\u0431\u0443\u0435\u0442\u0441\u044f.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    # Load into ChromaDB
    try:
        chunks_count = await _load_to_rag(text, category, title, filename)

        # Register in loaded documents list
        user_name = callback.from_user.full_name or str(callback.from_user.id)
        _register_document(filename, title, category, content_hash, chunks_count, user_name)

        cat_label = DOCUMENT_CATEGORIES.get(category, 'Прочее')
        await callback.message.edit_text(
            f"\u2705 <b>\u0414\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0441\u043e\u0445\u0440\u0430\u043d\u0451\u043d \u0432 \u0431\u0430\u0437\u0443 \u0437\u043d\u0430\u043d\u0438\u0439!</b>\n\n"
            f"\ud83d\udccc {title}\n"
            f"\ud83d\udcc1 \u041a\u0430\u0442\u0435\u0433\u043e\u0440\u0438\u044f: {cat_label}\n"
            f"\ud83e\udde9 \u0424\u0440\u0430\u0433\u043c\u0435\u043d\u0442\u043e\u0432: {chunks_count}\n\n"
            "\u0422\u0435\u043f\u0435\u0440\u044c AI-\u0430\u0433\u0435\u043d\u0442\u044b \u0431\u0443\u0434\u0443\u0442 \u0438\u0441\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u044c \u044d\u0442\u043e\u0442 \u0434\u043e\u043a\u0443\u043c\u0435\u043d\u0442 \u0434\u043b\u044f \u043e\u0442\u0432\u0435\u0442\u043e\u0432.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"RAG load error: {e}")
        await callback.message.edit_text(
            f"\u274c \u041e\u0448\u0438\u0431\u043a\u0430 \u043f\u0440\u0438 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u0438: {str(e)[:200]}",
        )

    await state.clear()


@document_router.callback_query(F.data == "doc_rename")
async def handle_doc_rename(callback: CallbackQuery, state: FSMContext):
    """Ask user for a new name."""
    await state.set_state(DocumentUploadStates.waiting_rename)
    await callback.answer()
    await callback.message.edit_text(
        "✏️ Введите новое название для документа:",
    )


@document_router.message(DocumentUploadStates.waiting_rename)
async def handle_rename_input(message: Message, state: FSMContext):
    """Process rename input."""
    new_title = message.text.strip()
    if not new_title:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
        return

    data = await state.get_data()
    await state.update_data(title=new_title)
    await state.set_state(DocumentUploadStates.waiting_confirmation)

    category = data.get("category", "other")
    category_emoji = DOCUMENT_CATEGORIES.get(category, "📁 Прочее")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="doc_save"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="doc_cancel"),
        ],
    ])

    await message.answer(
        f"📌 Новое название: <b>{new_title}</b>\n"
        f"📁 Категория: {category_emoji}\n\n"
        f"Сохранить?",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@document_router.callback_query(F.data == "doc_recat")
async def handle_doc_recat(callback: CallbackQuery, state: FSMContext):
    """Show category selection buttons."""
    await callback.answer()

    # Build category buttons (3 per row)
    buttons = []
    row = []
    for key, label in DOCUMENT_CATEGORIES.items():
        row.append(InlineKeyboardButton(text=label, callback_data=f"doc_cat_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(
        "Выберите категорию документа:",
        reply_markup=keyboard,
    )


@document_router.callback_query(F.data.startswith("doc_cat_"))
async def handle_category_select(callback: CallbackQuery, state: FSMContext):
    """Handle category selection."""
    category = callback.data.replace("doc_cat_", "")
    await state.update_data(category=category)
    await state.set_state(DocumentUploadStates.waiting_confirmation)

    data = await state.get_data()
    title = data.get("title", "Без названия")
    category_emoji = DOCUMENT_CATEGORIES.get(category, "📁 Прочее")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="doc_save"),
            InlineKeyboardButton(text="✏️ Переименовать", callback_data="doc_rename"),
        ],
        [
            InlineKeyboardButton(text="❌ Отмена", callback_data="doc_cancel"),
        ],
    ])

    await callback.answer()
    await callback.message.edit_text(
        f"📁 Категория: {category_emoji}\n"
        f"📌 Название: <b>{title}</b>\n\n"
        f"Сохранить в базу знаний?",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


@document_router.callback_query(F.data == "doc_cancel")
async def handle_doc_cancel(callback: CallbackQuery, state: FSMContext):
    """Cancel document upload."""
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.edit_text("❌ Загрузка документа отменена.")


# ============================================================
# Helper functions
# ============================================================

async def _classify_document(text: str, caption: str = "") -> dict:
    """Classify document using AI."""
    ollama = OllamaClient()

    # If user provided caption, use it as strong hint
    hint = ""
    if caption:
        hint = f"\n\nПОДПИСЬ ПОЛЬЗОВАТЕЛЯ: {caption}\n(Используй подпись как основной ориентир для классификации)"

    prompt = CLASSIFY_PROMPT.format(text=text[:2000]) + hint

    try:
        result = await ollama.generate(
            prompt=prompt,
            model="llama3.1:8b",
            system_prompt="Ты классификатор документов. Отвечай только JSON.",
            temperature=0.1,
        )

        # Parse JSON
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]

        # Find JSON in response
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start >= 0 and end > start:
            clean = clean[start:end]

        return json.loads(clean)
    except Exception as e:
        logger.error(f"Document classification error: {e}")
        return {"category": "other", "title": "Документ", "description": "Не удалось классифицировать"}


async def _load_to_rag(text: str, category: str, title: str, filename: str) -> int:
    """Split text into chunks and load into ChromaDB."""
    # Split into chunks of ~200 words
    words = text.split()
    chunk_size = 200
    overlap = 30
    chunks = []

    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        if len(chunk.strip()) > 50:
            chunks.append(chunk)

    if not chunks:
        chunks = [text[:5000]]

    # Load into ChromaDB via rag_service
    loaded = 0
    for i, chunk in enumerate(chunks):
        doc_id = f"{category}_{filename}_{i}"
        metadata = {
            "source": filename,
            "title": title,
            "category": category,
            "chunk_index": i,
            "agent": _category_to_agent(category),
        }

        success = rag_service.add_document(
            doc_id=doc_id,
            text=chunk,
            metadata=metadata,
        )
        if success:
            loaded += 1

    logger.info(f"Loaded {loaded}/{len(chunks)} chunks for '{title}' ({category})")
    return loaded


def _category_to_agent(category: str) -> str:
    """Map document category to relevant agent."""
    mapping = {
        "contract": "legal",
        "act": "finance",
        "regulation": "general",
        "normative": "safety",
        "request": "procurement",
        "protocol": "project_management",
        "report": "project_management",
        "letter": "general",
        "estimate": "finance",
        "safety": "safety",
        "hr": "hr",
        "other": "general",
    }
    return mapping.get(category, "general")
