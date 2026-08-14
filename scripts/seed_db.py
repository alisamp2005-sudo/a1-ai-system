"""
Seed script — populates the database with initial users, departments, and projects.
Run inside Docker: docker compose exec backend python -m scripts.seed_db
Or standalone: python scripts/seed_db.py
"""

import asyncio
import uuid
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.db.models import Base, User, Department, UserDepartment, Project, UserProject, RoutingRule

# Database URL (adjust for local or Docker)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://a1admin:A1system2026secure@localhost:5432/a1_system"
)


async def seed():
    """Seed the database with initial data."""
    engine = create_async_engine(DATABASE_URL)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # ============================================================
        # USERS
        # ============================================================
        users_data = [
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
                "full_name": "Алимов З.Т.",
                "phone_number": "+70000000001",
                "role": "top_manager",
                "telegram_id": None,
            },
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
                "full_name": "Зиновьева А.",
                "phone_number": "+70000000002",
                "role": "top_manager",
                "telegram_id": None,
            },
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
                "full_name": "Лыков М.А.",
                "phone_number": "+70000000003",
                "role": "top_manager",
                "telegram_id": None,
            },
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000004"),
                "full_name": "Поляков С.Б.",
                "phone_number": "+70000000004",
                "role": "manager",
                "telegram_id": None,
            },
            {
                "id": uuid.UUID("00000000-0000-0000-0000-000000000005"),
                "full_name": "Администратор (Тест)",
                "phone_number": "+70000000005",
                "role": "admin",
                "telegram_id": "5867249984",
            },
        ]

        for u_data in users_data:
            user = User(**u_data)
            session.add(user)

        print(f"✅ Создано {len(users_data)} пользователей")

        # ============================================================
        # DEPARTMENTS
        # ============================================================
        departments_data = [
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
                "name": "Руководство",
                "head_id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000002"),
                "name": "Служба ТБ",
                "head_id": uuid.UUID("00000000-0000-0000-0000-000000000004"),
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
                "name": "Производство",
                "head_id": uuid.UUID("00000000-0000-0000-0000-000000000003"),
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000004"),
                "name": "Снабжение",
                "head_id": None,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000005"),
                "name": "Финансы",
                "head_id": None,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000006"),
                "name": "Юридический",
                "head_id": None,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000007"),
                "name": "HR",
                "head_id": None,
            },
        ]

        for d_data in departments_data:
            dept = Department(**d_data)
            session.add(dept)

        print(f"✅ Создано {len(departments_data)} отделов")

        # ============================================================
        # USER-DEPARTMENT LINKS
        # ============================================================
        user_dept_links = [
            ("00000000-0000-0000-0000-000000000001", "10000000-0000-0000-0000-000000000001"),
            ("00000000-0000-0000-0000-000000000002", "10000000-0000-0000-0000-000000000001"),
            ("00000000-0000-0000-0000-000000000003", "10000000-0000-0000-0000-000000000003"),
            ("00000000-0000-0000-0000-000000000004", "10000000-0000-0000-0000-000000000002"),
        ]

        for user_id, dept_id in user_dept_links:
            link = UserDepartment(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                department_id=uuid.UUID(dept_id),
            )
            session.add(link)

        print(f"✅ Связано {len(user_dept_links)} пользователей с отделами")

        # ============================================================
        # PROJECTS (строительные объекты — первые 5 для теста)
        # ============================================================
        projects_data = [
            {
                "id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
                "name": "Михалковская",
                "address": "г. Москва, ул. Михалковская",
                "status": "active",
            },
            {
                "id": uuid.UUID("20000000-0000-0000-0000-000000000002"),
                "name": "Хорошевское шоссе",
                "address": "г. Москва, Хорошевское шоссе",
                "status": "active",
            },
            {
                "id": uuid.UUID("20000000-0000-0000-0000-000000000003"),
                "name": "Варшавское шоссе",
                "address": "г. Москва, Варшавское шоссе",
                "status": "active",
            },
            {
                "id": uuid.UUID("20000000-0000-0000-0000-000000000004"),
                "name": "Ленинградский проспект",
                "address": "г. Москва, Ленинградский проспект",
                "status": "active",
            },
            {
                "id": uuid.UUID("20000000-0000-0000-0000-000000000005"),
                "name": "Рязанский проспект",
                "address": "г. Москва, Рязанский проспект",
                "status": "active",
            },
        ]

        for p_data in projects_data:
            project = Project(**p_data)
            session.add(project)

        print(f"✅ Создано {len(projects_data)} объектов")

        # ============================================================
        # ROUTING RULES (матрица назначения)
        # ============================================================
        routing_rules = [
            {
                "task_type": "safety",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000002"),
                "default_assignee_id": uuid.UUID("00000000-0000-0000-0000-000000000004"),
                "default_priority": "P1",
            },
            {
                "task_type": "procurement",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000004"),
                "default_priority": "P2",
            },
            {
                "task_type": "hr",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000007"),
                "default_priority": "P2",
            },
            {
                "task_type": "finance",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000005"),
                "default_priority": "P2",
            },
            {
                "task_type": "legal",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000006"),
                "default_priority": "P2",
            },
            {
                "task_type": "project_management",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
                "default_priority": "P2",
            },
            {
                "task_type": "reporting",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
                "default_priority": "P3",
            },
            {
                "task_type": "general",
                "department_id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
                "default_assignee_id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
                "default_priority": "P3",
            },
        ]

        for r_data in routing_rules:
            rule = RoutingRule(id=uuid.uuid4(), **r_data)
            session.add(rule)

        print(f"✅ Создано {len(routing_rules)} правил маршрутизации")

        # ============================================================
        # COMMIT
        # ============================================================
        await session.commit()
        print("\n🎉 База данных заполнена успешно!")
        print("\nПользователи:")
        for u in users_data:
            tg = f" (TG: {u['telegram_id']})" if u['telegram_id'] else ""
            print(f"  • {u['full_name']} [{u['role']}]{tg}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
