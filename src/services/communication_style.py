"""Role-aware wording for Telegram bot replies."""

from typing import Optional, Protocol


class EmployeeLike(Protocol):
    """Minimal employee shape required for communication personalization."""

    job_title: str


def is_general_director(employee: Optional[EmployeeLike]) -> bool:
    """Return True only for the employee recorded as General Director."""
    return bool(employee and employee.job_title.strip().casefold() == "генеральный директор")


def greeting_for(employee: Optional[EmployeeLike]) -> str:
    """Return the appropriate start greeting without changing other staff wording."""
    if is_general_director(employee):
        return (
            "👋 <b>Привет, Босс!</b>\n\n"
            "Я на связи. Чем могу помочь: проверить объект, найти документ, "
            "поставить задачу или подготовить сводку?"
        )
    return "👋 <b>Добро пожаловать в AI-систему А1!</b>"


def format_reply(text: str, employee: Optional[EmployeeLike]) -> str:
    """Prefix substantive replies for the General Director in a concise business style."""
    if is_general_director(employee):
        return f"<b>Босс,</b>\n\n{text}"
    return text
