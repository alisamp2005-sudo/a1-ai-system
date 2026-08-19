"""Validate the manually supplied employee roster before production import."""

import json
from pathlib import Path


ROSTER_PATH = Path(__file__).resolve().parents[1] / "config" / "employee_roster.json"


def run() -> None:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    employees = roster["employees"]

    assert len(employees) == 19
    assert len({employee["full_name"] for employee in employees}) == len(employees)
    assert all(employee["department"] in roster["departments"] for employee in employees)
    assert all(employee["role"] in {"top_manager", "manager", "worker", "admin"} for employee in employees)
    assert all(employee.get("telegram_id") or employee.get("telegram_username") for employee in employees)
    assert {"АХО", "Снабжение", "ПТО"}.issubset(roster["department_categories"])
    print("Employee roster checks passed")


if __name__ == "__main__":
    run()
