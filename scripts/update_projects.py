"""
Update projects — replaces test objects with real 16 construction sites.
Run: cd ~/a1-ai-system && python3 scripts/update_projects.py
"""

import asyncio
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.db.models import Base, Project

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://a1admin:A1system2026secure@localhost:5432/a1_system"
)

# Реальные объекты А1 (из Яндекс.Диска + Реестр контрактов 2026)
REAL_PROJECTS = [
    {
        "name": '"Дом юстиции" г. Великий Новгород',
        "address": "г. Великий Новгород",
        "status": "active",
        "description": "Строительство Дома юстиции",
    },
    {
        "name": 'АО "ГАЗСТРОЙПРОМ" Минск',
        "address": "г. Минск, Беларусь",
        "status": "active",
        "description": "Объект АО ГАЗСТРОЙПРОМ",
    },
    {
        "name": 'АО "ЩЛЗ" Лифты',
        "address": "г. Москва",
        "status": "active",
        "description": "Щербинский лифтостроительный завод — лифтовое оборудование",
    },
    {
        "name": 'АО "ЩЛЗ" Стройка',
        "address": "г. Москва",
        "status": "active",
        "description": "Щербинский лифтостроительный завод — строительные работы",
    },
    {
        "name": "Алые паруса",
        "address": "г. Москва",
        "status": "active",
        "description": "ЖК Алые паруса",
    },
    {
        "name": "ДРОЗ",
        "address": "г. Москва",
        "status": "active",
        "description": "ГБУ Дирекция развития объектов здравоохранения города Москвы",
    },
    {
        "name": 'ЖК «ЛДМ» СПБ',
        "address": "г. Санкт-Петербург",
        "status": "active",
        "description": "Жилой комплекс ЛДМ в Санкт-Петербурге",
    },
    {
        "name": "Кубинка",
        "address": "Московская обл., г. Кубинка",
        "status": "active",
        "description": "Объект в Кубинке",
    },
    {
        "name": "Ленская 15",
        "address": "г. Москва, ул. Ленская, д. 15",
        "status": "active",
        "description": "Строительство жилого дома",
    },
    {
        "name": "Мосводосток Дмитровское шоссе",
        "address": "г. Москва, Дмитровское шоссе",
        "status": "active",
        "description": "Технологическое присоединение к системе водоотведения. Жилой дом с подземным гаражом.",
    },
    {
        "name": "Остров-8",
        "address": "г. Москва",
        "status": "active",
        "description": "Строительный объект Остров-8. Генподряд.",
    },
    {
        "name": "ППК ВСК (Ульяновск, Поливно)",
        "address": "Ульяновская обл., с. Поливно",
        "status": "active",
        "description": "Объект ППК ВСК в Ульяновской области",
    },
    {
        "name": "ППК ВСК (Чебаркуль)",
        "address": "Челябинская обл., г. Чебаркуль",
        "status": "active",
        "description": "Объект ППК ВСК в Чебаркуле",
    },
    {
        "name": "Хранилища",
        "address": "г. Москва",
        "status": "active",
        "description": "Строительство хранилищ",
    },
    {
        "name": "Реновация (Михалковская)",
        "address": "г. Москва, ул. Михалковская, вл. 52, стр. 22, 23",
        "status": "active",
        "description": "Московский фонд реновации. Договор №73-0525-КЭФ-ДРТ30. Сумма: 2,157,325,555 руб. ПИР до 01.03.2026, СМР до 01.03.2028.",
    },
    {
        "name": "ул. Житная (ФБУ РФЦСЭ при Минюсте)",
        "address": "г. Москва, 4-й Крутицкий пер., д.10, стр.1",
        "status": "active",
        "description": "Реконструкция здания под лабораторный корпус ФБУ РФЦСЭ. Контракт 3К/2021. Сумма: 1,981,045,262.76 руб.",
    },
]


async def update_projects():
    """Replace test projects with real ones."""
    engine = create_async_engine(DATABASE_URL)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Delete old test projects
        await session.execute(text("DELETE FROM user_projects"))
        await session.execute(text("DELETE FROM projects"))
        await session.commit()
        print("🗑  Удалены старые тестовые объекты")

        # Add real projects
        for i, p_data in enumerate(REAL_PROJECTS, 1):
            project = Project(
                id=uuid.UUID(f"20000000-0000-0000-0000-{i:012d}"),
                name=p_data["name"],
                address=p_data.get("address"),
                status=p_data.get("status", "active"),
            )
            session.add(project)

        await session.commit()
        print(f"✅ Добавлено {len(REAL_PROJECTS)} реальных объектов:")
        for i, p in enumerate(REAL_PROJECTS, 1):
            print(f"   {i:2d}. {p['name']}")

    await engine.dispose()
    print("\n🎉 База объектов обновлена!")


if __name__ == "__main__":
    asyncio.run(update_projects())
