"""
Inline Links Service — auto-detects entities (objects, users) in bot responses
and generates inline keyboard buttons linking to their Mini App cards.
"""

import re
import logging
from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

logger = logging.getLogger(__name__)

# Base URL for Mini App cards
MINIAPP_BASE_URL = "https://ai.bruceli.ru/miniapp"

# Known objects — real company objects
KNOWN_OBJECTS = [
    "Дом юстиции",
    "ГАЗСТРОЙПРОМ",
    "ЩЛЗ Лифты",
    "ЩЛЗ Стройка",
    "Алые паруса",
    "ДРОЗ",
    "ЖК ЛДМ",
    "Кубинка",
    "Ленская 15",
    "Мосводосток",
    "Остров-8",
    "ППК ВСК",
    "Хранилища",
    "Реновация",
    "Михалковская",
    "Житная",
]

# Known people (will be loaded from DB in future)
KNOWN_PEOPLE = [
    "Алимов", "Зиновьева", "Лыков", "Поляков",
]


def detect_entities(text: str) -> dict:
    """
    Detect mentioned objects and people in the response text.

    Returns:
        {"objects": ["Остров-8", ...], "people": ["Поляков", ...]}
    """
    found_objects = []
    found_people = []

    text_lower = text.lower()

    for obj in KNOWN_OBJECTS:
        if obj.lower() in text_lower:
            found_objects.append(obj)

    for person in KNOWN_PEOPLE:
        if person.lower() in text_lower:
            found_people.append(person)

    return {"objects": found_objects, "people": found_people}


def build_inline_keyboard(text: str) -> Optional[InlineKeyboardMarkup]:
    """
    Build inline keyboard with entity links based on response text.
    Returns None if no entities detected.

    If there are more than 8 entities — don't show buttons (too many, clutters the chat).
    If listing all objects — skip buttons (user already sees the full list).
    """
    entities = detect_entities(text)
    objects = entities["objects"]
    people = entities["people"]

    if not objects and not people:
        return None

    # If too many objects mentioned (e.g. full list) — skip buttons
    if len(objects) > 6:
        return None

    buttons = []

    # Add object buttons (all found, up to 6)
    for obj in objects[:6]:
        buttons.append(
            InlineKeyboardButton(
                text=f"🏗 {obj}",
                web_app=WebAppInfo(url=f"{MINIAPP_BASE_URL}/object/{obj}")
            )
        )

    # Add people buttons (up to 4)
    for person in people[:4]:
        buttons.append(
            InlineKeyboardButton(
                text=f"👤 {person}",
                web_app=WebAppInfo(url=f"{MINIAPP_BASE_URL}/user/{person}")
            )
        )

    if not buttons:
        return None

    # Arrange buttons in rows (max 2 per row for readability)
    rows = []
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i+2])

    return InlineKeyboardMarkup(inline_keyboard=rows)
