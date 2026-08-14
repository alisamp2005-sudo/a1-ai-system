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

# Known objects (will be loaded from DB in future)
KNOWN_OBJECTS = [
    "Михалковская", "Дмитровская", "Южнопортовая",
    "Нагатинская", "Кунцевская", "Хорошевское",
    "Варшавское", "Ленинградский", "Рязанский",
]

# Known people (will be loaded from DB in future)
KNOWN_PEOPLE = [
    "Алимов", "Зиновьева", "Лыков", "Поляков",
]


def detect_entities(text: str) -> dict:
    """
    Detect mentioned objects and people in the response text.
    
    Returns:
        {"objects": ["Нагатинская", ...], "people": ["Поляков", ...]}
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
    
    Buttons open Mini App cards for objects/users.
    """
    entities = detect_entities(text)
    objects = entities["objects"]
    people = entities["people"]

    if not objects and not people:
        return None

    buttons = []

    # Add object buttons (max 3)
    for obj in objects[:3]:
        buttons.append(
            InlineKeyboardButton(
                text=f"🏗 {obj}",
                web_app=WebAppInfo(url=f"{MINIAPP_BASE_URL}/object/{obj}")
            )
        )

    # Add people buttons (max 2)
    for person in people[:2]:
        buttons.append(
            InlineKeyboardButton(
                text=f"👤 {person}",
                web_app=WebAppInfo(url=f"{MINIAPP_BASE_URL}/user/{person}")
            )
        )

    if not buttons:
        return None

    # Arrange buttons in rows (max 3 per row)
    rows = []
    for i in range(0, len(buttons), 3):
        rows.append(buttons[i:i+3])

    return InlineKeyboardMarkup(inline_keyboard=rows)
