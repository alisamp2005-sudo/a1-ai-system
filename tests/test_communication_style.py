"""Regression checks for General Director wording."""

from dataclasses import dataclass

from src.services.communication_style import format_reply, greeting_for


@dataclass
class EmployeeIdentity:
    user_id: str
    full_name: str
    role: str
    job_title: str


def run() -> None:
    boss = EmployeeIdentity(
        user_id="1",
        full_name="Загир Алимович Тагиров",
        role="top_manager",
        job_title="Генеральный директор",
    )
    manager = EmployeeIdentity(
        user_id="2",
        full_name="Соболь Владислав Эдуардович",
        role="manager",
        job_title="Руководитель отдела снабжения",
    )

    assert "Привет, Босс" in greeting_for(boss)
    assert "Босс" in format_reply("Готово.", boss)
    assert "Босс" not in greeting_for(manager)
    assert format_reply("Готово.", manager) == "Готово."
    print("Communication style checks passed")


if __name__ == "__main__":
    run()
