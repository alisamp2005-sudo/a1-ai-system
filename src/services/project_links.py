"""Canonical links between names used in chat and Project names stored in PostgreSQL."""

from urllib.parse import quote

MINIAPP_BASE_URL = "https://ai.bruceli.ru/miniapp"

# Chat aliases may be short; routes always use the exact database project name.
PROJECT_ALIASES = {
    "Дом юстиции": '"Дом юстиции" г. Великий Новгород',
    "ГАЗСТРОЙПРОМ": 'АО "ГАЗСТРОЙПРОМ" Минск',
    "ЩЛЗ Лифты": 'АО "ЩЛЗ" Лифты',
    "ЩЛЗ Стройка": 'АО "ЩЛЗ" Стройка',
    "Алые паруса": "Алые паруса",
    "ДРОЗ": "ДРОЗ",
    "ЖК ЛДМ": "ЖК «ЛДМ» СПБ",
    "Кубинка": "Кубинка",
    "Ленская 15": "Ленская 15",
    "Мосводосток": "Мосводосток Дмитровское шоссе",
    "Остров-8": "Остров-8",
    "ППК ВСК": "ППК ВСК (Чебаркуль)",
    "Хранилища": "Хранилища",
    "Реновация": "Реновация (Михалковская)",
    "Михалковская": "Реновация (Михалковская)",
    "Житная": "ул. Житная (ФБУ РФЦСЭ при Минюсте)",
}


def canonical_project_name(alias_or_name: str) -> str:
    """Resolve a chat alias to the exact name used by the Project table."""
    return PROJECT_ALIASES.get(alias_or_name, alias_or_name)


def object_card_url(alias_or_name: str) -> str:
    """Return a unique, URL-encoded Mini App URL for one project card."""
    project_name = canonical_project_name(alias_or_name)
    encoded = quote(project_name, safe="")
    # The query parameter prevents Telegram WebApp re-use from restoring a card
    # opened by another object button during the same chat session.
    return f"{MINIAPP_BASE_URL}/object/{encoded}?entity={encoded}"
