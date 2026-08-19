"""Import the approved A1 employee roster into PostgreSQL.

Run on the Mac:
    cd ~/a1-ai-system && python3 scripts/import_employee_roster.py

The script is idempotent: repeated runs update the supplied records and do not
create duplicate employee, department, or project-membership rows.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.db.models import Department, Project, User, UserDepartment, UserProject

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://a1admin:A1system2026secure@localhost:5432/a1_system",
)
ROSTER_PATH = Path(__file__).resolve().parents[1] / "config" / "employee_roster.json"


async def get_or_create_department(session: AsyncSession, name: str) -> Department:
    result = await session.execute(select(Department).where(Department.name == name))
    department = result.scalar_one_or_none()
    if not department:
        department = Department(name=name)
        session.add(department)
        await session.flush()
    return department


async def find_employee(session: AsyncSession, payload: dict) -> User | None:
    telegram_id = payload.get("telegram_id")
    telegram_username = payload.get("telegram_username")
    full_name = payload["full_name"]

    if telegram_id:
        result = await session.execute(select(User).where(User.telegram_id == str(telegram_id)))
        employee = result.scalar_one_or_none()
        if employee:
            return employee
    if telegram_username:
        result = await session.execute(
            select(User).where(User.telegram_username.ilike(telegram_username))
        )
        employee = result.scalar_one_or_none()
        if employee:
            return employee

    result = await session.execute(select(User).where(User.full_name == full_name))
    employee = result.scalar_one_or_none()
    if employee:
        return employee

    for legacy_name in payload.get("legacy_full_names", []):
        result = await session.execute(select(User).where(User.full_name == legacy_name))
        employee = result.scalar_one_or_none()
        if employee:
            return employee
    return None


async def upsert_roster() -> None:
    roster = json.loads(ROSTER_PATH.read_text(encoding="utf-8"))
    engine = create_async_engine(DATABASE_URL)

    async with engine.begin() as connection:
        # Safe schema additions for databases created before these fields existed.
        await connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(255)"
        ))
        await connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS job_title VARCHAR(255)"
        ))

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    created = updated = departments_created = links_created = project_links_created = 0

    async with session_factory() as session:
        existing_department_names = {
            name for name in (await session.execute(select(Department.name))).scalars().all()
        }
        departments = {}
        for department_name in roster["departments"]:
            departments[department_name] = await get_or_create_department(session, department_name)
            if department_name not in existing_department_names:
                departments_created += 1

        department_heads: dict[str, User] = {}
        for payload in roster["employees"]:
            employee = await find_employee(session, payload)
            if employee is None:
                employee = User(full_name=payload["full_name"], role=payload["role"], is_active=True)
                session.add(employee)
                created += 1
            else:
                updated += 1

            employee.full_name = payload["full_name"]
            employee.telegram_id = str(payload["telegram_id"]) if payload.get("telegram_id") else employee.telegram_id
            employee.telegram_username = payload.get("telegram_username") or employee.telegram_username
            employee.job_title = payload["job_title"]
            employee.role = payload["role"]
            employee.is_active = True
            await session.flush()

            department = departments[payload["department"]]
            membership = await session.execute(
                select(UserDepartment).where(
                    UserDepartment.user_id == employee.id,
                    UserDepartment.department_id == department.id,
                )
            )
            if not membership.scalar_one_or_none():
                session.add(UserDepartment(user_id=employee.id, department_id=department.id))
                links_created += 1

            if "Руководитель" in payload["job_title"] or payload["role"] == "top_manager":
                department_heads.setdefault(payload["department"], employee)

            for project_name in payload.get("projects", []):
                result = await session.execute(select(Project).where(Project.name == project_name))
                project = result.scalars().first()
                if not project:
                    print(f"⚠️ Объект не найден, связь пропущена: {project_name} → {employee.full_name}")
                    continue
                membership = await session.execute(
                    select(UserProject).where(
                        UserProject.user_id == employee.id,
                        UserProject.project_id == project.id,
                    )
                )
                if not membership.scalar_one_or_none():
                    session.add(UserProject(user_id=employee.id, project_id=project.id, is_default=True))
                    project_links_created += 1
                if "Руководитель проекта" in payload["job_title"] and not project.manager_id:
                    project.manager_id = employee.id

        for department_name, head in department_heads.items():
            departments[department_name].head_id = head.id

        await session.commit()

    await engine.dispose()
    print("✅ Импорт сотрудников завершён")
    print(f"   Создано: {created}; обновлено: {updated}")
    print(f"   Новых отделов: {departments_created}")
    print(f"   Связей сотрудник–отдел: {links_created}")
    print(f"   Связей сотрудник–объект: {project_links_created}")


if __name__ == "__main__":
    asyncio.run(upsert_roster())
