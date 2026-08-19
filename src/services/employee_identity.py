"""Telegram identity resolution for the approved A1 employee roster."""

import logging
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, select

from src.db.models import User
from src.db.session import async_session_factory

logger = logging.getLogger(__name__)


@dataclass
class EmployeeIdentity:
    """Minimal identity context passed to bot handlers after roster lookup."""

    user_id: str
    full_name: str
    role: str
    job_title: str
    department: Optional[str] = None


def normalize_username(username: Optional[str]) -> str:
    """Store Telegram usernames without @ and compare them case-insensitively."""
    return (username or "").strip().lstrip("@").casefold()


async def resolve_employee(telegram_id: str, telegram_username: Optional[str]) -> Optional[EmployeeIdentity]:
    """Resolve an active employee and bind a preapproved username to its first real ID.

    A record that already has telegram_id is matched only by that immutable ID.
    A roster record containing only a Telegram username is bound to the first
    matching Telegram account and subsequently identified by ID.
    """
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(
                    User.telegram_id == str(telegram_id),
                    User.is_active.is_(True),
                )
            )
            employee = result.scalar_one_or_none()

            if not employee:
                username = normalize_username(telegram_username)
                if not username:
                    return None

                result = await session.execute(
                    select(User).where(
                        func.lower(User.telegram_username) == username,
                        User.is_active.is_(True),
                    )
                )
                employee = result.scalar_one_or_none()
                if not employee:
                    return None

                # First confirmed incoming account wins the ID binding. The
                # username remains stored for administrative visibility.
                if employee.telegram_id:
                    return None
                employee.telegram_id = str(telegram_id)
                await session.commit()
                logger.info("Bound Telegram ID for employee %s", employee.full_name)

            return EmployeeIdentity(
                user_id=str(employee.id),
                full_name=employee.full_name,
                role=employee.role,
                job_title=getattr(employee, "job_title", "") or "",
            )
    except Exception as exc:
        logger.exception("Employee identity resolution failed: %s", exc)
        return None
