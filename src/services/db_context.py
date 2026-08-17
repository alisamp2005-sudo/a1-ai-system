"""
DB Context Service — предоставляет агентам данные из PostgreSQL.
Используется для получения информации об объектах, сотрудниках и задачах.
"""

import logging
from typing import Optional

from sqlalchemy import select, text
from src.db.session import async_session_factory
from src.db.models import Project, User, Department

logger = logging.getLogger(__name__)


class DBContext:
    """Provides database context for AI agents."""

    async def get_projects_context(self) -> str:
        """Get all active projects as text context for agents."""
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Project).where(Project.status == "active")
                )
                projects = result.scalars().all()

                if not projects:
                    return "В базе данных нет активных объектов."

                lines = ["ОБЪЕКТЫ КОМПАНИИ А1 (из базы данных):"]
                for p in projects:
                    addr = p.address if p.address else "адрес не указан"
                    status = p.status or "active"
                    lines.append(f"• {p.name} — {addr} (статус: {status})")

                return "\n".join(lines)
        except Exception as e:
            logger.warning(f"DB context error (projects): {e}")
            return ""

    async def get_project_by_name(self, name: str) -> str:
        """Find active project by name (partial match) and return details."""
        try:
            async with async_session_factory() as session:
                # Only show active projects to the bot
                result = await session.execute(
                    select(Project).where(
                        Project.name.ilike(f"%{name}%"),
                        Project.status == "active"
                    )
                )
                project = result.scalars().first()

                if not project:
                    return f"Объект «{name}» не найден среди активных объектов. Возможно, он завершён или данные ещё не загружены."

                # Get manager info
                manager_name = "не назначен"
                if project.manager_id:
                    mgr_result = await session.execute(
                        select(User).where(User.id == project.manager_id)
                    )
                    manager = mgr_result.scalars().first()
                    if manager:
                        manager_name = manager.full_name

                addr = project.address if project.address else "не указан"
                return (
                    f"ОБЪЕКТ: {project.name}\n"
                    f"Адрес: {addr}\n"
                    f"Статус: {project.status}\n"
                    f"Ответственный: {manager_name}"
                )
        except Exception as e:
            logger.warning(f"DB context error (project_by_name): {e}")
            return ""

    async def get_users_context(self) -> str:
        """Get all active users as text context."""
        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.is_active == True)
                )
                users = result.scalars().all()

                if not users:
                    return "В базе данных нет сотрудников."

                lines = ["СОТРУДНИКИ КОМПАНИИ А1:"]
                for u in users:
                    role_ru = {
                        "admin": "Администратор",
                        "top_manager": "Руководство",
                        "manager": "Руководитель",
                        "worker": "Сотрудник",
                    }.get(u.role, u.role)
                    lines.append(f"• {u.full_name} — {role_ru}")

                return "\n".join(lines)
        except Exception as e:
            logger.warning(f"DB context error (users): {e}")
            return ""


# Singleton
db_context = DBContext()
